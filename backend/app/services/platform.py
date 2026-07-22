"""Platform-operator (super-admin) operations that span ALL organizations.

This is the one service that intentionally crosses org boundaries, so every
mutation is audited under the target org.
"""
import uuid
from datetime import timedelta

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_view_as_token, generate_opaque_token, hash_password
from app.models import (
    AuditLog,
    Conversation,
    Device,
    Message,
    Organization,
    RemediationTask,
    RemediationStatus,
    SubscriptionStatus,
    User,
    UserRole,
)
from app.models.base import as_utc, utcnow
from app.repositories.organizations import OrganizationRepository
from app.repositories.users import UserRepository
from app.schemas.devices import ONLINE_THRESHOLD
from app.schemas.platform import (
    ActionStat,
    MonthCount,
    OrganizationAdminRead,
    OrganizationCreate,
    OrganizationUpdate,
    OrgDeviceStat,
    PlatformAuditRead,
    PlatformBilling,
    PlatformBillingRow,
    PlatformOverview,
    PlatformReports,
    ProviderStat,
    ViewAsToken,
)
from app.services.audit import AuditService
from app.services.email import EmailService
from app.services.exceptions import ConflictError
from app.services.subscription import TRIAL_DAYS
from app.services.exceptions import NotFoundError


class PlatformService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.orgs = OrganizationRepository(session)
        self.audit = AuditService(session)

    async def _platform_org_ids(self) -> set[uuid.UUID]:
        """Organizations that contain a platform admin are the operator's OWN internal
        workspace — not paying customers. They're excluded from every customer-facing
        list and revenue/growth rollup so the operator's own org never shows up as a
        customer or distorts the numbers."""
        return set((await self.session.execute(
            select(User.org_id).where(User.is_platform_admin.is_(True)).distinct()
        )).scalars().all())

    async def list_organizations(self) -> list[OrganizationAdminRead]:
        platform_ids = await self._platform_org_ids()
        orgs = [
            o for o in (await self.session.execute(
                select(Organization).order_by(Organization.created_at)
            )).scalars().all()
            if o.id not in platform_ids
        ]
        user_counts = dict(
            (await self.session.execute(select(User.org_id, func.count()).group_by(User.org_id))).all()
        )
        device_counts = dict(
            (await self.session.execute(select(Device.org_id, func.count()).group_by(Device.org_id))).all()
        )
        result: list[OrganizationAdminRead] = []
        for org in orgs:
            read = OrganizationAdminRead.model_validate(org)
            read.user_count = user_counts.get(org.id, 0)
            read.device_count = device_counts.get(org.id, 0)
            result.append(read)
        return result

    async def overview(self) -> PlatformOverview:
        """Aggregate stats across all CUSTOMER organizations for the operator's landing
        view (the operator's own internal org is excluded)."""
        now = utcnow()
        platform_ids = await self._platform_org_ids()
        # `.where(*[])` is a no-op, so these degrade cleanly when there are no internal orgs.
        org_excl = [Organization.id.notin_(platform_ids)] if platform_ids else []
        dev_excl = [Device.org_id.notin_(platform_ids)] if platform_ids else []
        user_excl = [User.org_id.notin_(platform_ids)] if platform_ids else []
        rem_excl = [RemediationTask.org_id.notin_(platform_ids)] if platform_ids else []

        total_orgs = (await self.session.execute(
            select(func.count()).select_from(Organization).where(*org_excl)
        )).scalar_one()

        status_rows = (await self.session.execute(
            select(Organization.subscription_status, func.count())
            .where(*org_excl).group_by(Organization.subscription_status)
        )).all()
        orgs_by_status = {getattr(s, "value", s): n for s, n in status_rows}

        trials_ending = (await self.session.execute(
            select(func.count()).select_from(Organization).where(
                Organization.subscription_status == SubscriptionStatus.TRIALING,
                Organization.trial_ends_at.is_not(None),
                Organization.trial_ends_at >= now,
                Organization.trial_ends_at <= now + timedelta(days=7),
                *org_excl,
            )
        )).scalar_one()

        total_users = (await self.session.execute(
            select(func.count()).select_from(User).where(*user_excl)
        )).scalar_one()
        total_devices = (await self.session.execute(
            select(func.count()).select_from(Device).where(*dev_excl)
        )).scalar_one()
        online = (await self.session.execute(
            select(func.count()).select_from(Device).where(
                Device.last_seen_at.is_not(None),
                Device.last_seen_at >= now - ONLINE_THRESHOLD,
                *dev_excl,
            )
        )).scalar_one()
        licenses = (await self.session.execute(
            select(func.coalesce(func.sum(Organization.license_count), 0)).where(*org_excl)
        )).scalar_one()
        pending = (await self.session.execute(
            select(func.count()).select_from(RemediationTask).where(
                RemediationTask.status == RemediationStatus.PENDING_APPROVAL,
                *rem_excl,
            )
        )).scalar_one()

        signups_30d = (await self.session.execute(
            select(func.count()).select_from(Organization).where(
                Organization.created_at >= now - timedelta(days=30),
                *org_excl,
            )
        )).scalar_one()

        # Revenue: only ACTIVE (paying) orgs contribute; apply each org's discount.
        active_rows = (await self.session.execute(
            select(Organization.license_count, Organization.discount_percent).where(
                Organization.subscription_status == SubscriptionStatus.ACTIVE,
                *org_excl,
            )
        )).all()
        active_subscriptions = len(active_rows)
        price = get_settings().price_per_seat_cents
        mrr_cents = None
        if price:
            mrr_cents = sum(
                round((lc or 0) * price * (100 - (disc or 0)) / 100)
                for lc, disc in active_rows
            )

        return PlatformOverview(
            total_organizations=total_orgs,
            orgs_by_status=orgs_by_status,
            trials_ending_7d=trials_ending,
            signups_30d=signups_30d,
            active_subscriptions=active_subscriptions,
            mrr_cents=mrr_cents,
            total_users=total_users,
            total_devices=total_devices,
            online_devices=online,
            offline_devices=total_devices - online,
            licenses_sold=int(licenses),
            remediation_pending=pending,
        )

    async def billing(self) -> PlatformBilling:
        """Platform-wide revenue rollup: per-org economics + MRR/ARR + provider mix."""
        price = get_settings().price_per_seat_cents
        platform_ids = await self._platform_org_ids()
        orgs = [
            o for o in (await self.session.execute(
                select(Organization).order_by(Organization.created_at)
            )).scalars().all()
            if o.id not in platform_ids
        ]

        rows: list[PlatformBillingRow] = []
        by_status: dict[str, int] = {}
        by_provider: dict[str, dict[str, int]] = {}
        total_mrr = 0
        for org in orgs:
            status_val = org.subscription_status.value
            by_status[status_val] = by_status.get(status_val, 0) + 1

            seat = None
            mrr = None
            if price is not None:
                seat = round(price * (100 - (org.discount_percent or 0)) / 100)
                mrr = seat * (org.license_count or 0) if (
                    org.subscription_status == SubscriptionStatus.ACTIVE
                ) else 0
                total_mrr += mrr
            if org.subscription_status == SubscriptionStatus.ACTIVE:
                provider = org.billing_provider or "manual"
                stat = by_provider.setdefault(provider, {"subscriptions": 0, "mrr_cents": 0})
                stat["subscriptions"] += 1
                stat["mrr_cents"] += mrr or 0

            rows.append(PlatformBillingRow(
                id=org.id, name=org.name, plan=org.plan,
                subscription_status=org.subscription_status,
                billing_provider=org.billing_provider,
                license_count=org.license_count or 0,
                discount_percent=org.discount_percent,
                seat_price_cents=seat, mrr_cents=mrr,
                current_period_end=org.current_period_end,
                trial_ends_at=org.trial_ends_at, created_at=org.created_at,
            ))

        return PlatformBilling(
            price_per_seat_cents=price,
            mrr_cents=total_mrr if price is not None else None,
            arr_cents=total_mrr * 12 if price is not None else None,
            active_subscriptions=by_status.get("active", 0),
            trialing=by_status.get("trialing", 0),
            past_due=by_status.get("past_due", 0),
            suspended=by_status.get("suspended", 0),
            canceled=by_status.get("canceled", 0),
            by_provider={
                p: ProviderStat(
                    subscriptions=s["subscriptions"],
                    mrr_cents=s["mrr_cents"] if price is not None else None,
                )
                for p, s in by_provider.items()
            },
            rows=rows,
        )

    async def reports(self) -> PlatformReports:
        """Cross-org analytics: growth, self-healing outcomes, fleet, AI volume."""
        from app.services.remediation.actions import ACTIONS  # local: avoid import cycles

        now = utcnow()
        cutoff_30d = now - timedelta(days=30)
        platform_ids = await self._platform_org_ids()
        org_excl = [Organization.id.notin_(platform_ids)] if platform_ids else []
        dev_excl = [Device.org_id.notin_(platform_ids)] if platform_ids else []
        rem_excl = [RemediationTask.org_id.notin_(platform_ids)] if platform_ids else []
        conv_excl = [Conversation.org_id.notin_(platform_ids)] if platform_ids else []

        # Growth: bucket org signups by calendar month (12 months incl. current).
        created = (await self.session.execute(
            select(Organization.created_at).where(*org_excl)
        )).scalars().all()
        months: list[str] = []
        y, m = now.year, now.month
        for _ in range(12):
            months.append(f"{y:04d}-{m:02d}")
            m -= 1
            if m == 0:
                y, m = y - 1, 12
        months.reverse()
        counts = {mo: 0 for mo in months}
        for ts in created:
            key = f"{ts.year:04d}-{ts.month:02d}"
            if key in counts:
                counts[key] += 1
        signups = [MonthCount(month=mo, count=counts[mo]) for mo in months]

        # Self-healing outcomes over the last 30 days.
        async def _count_rem(*where) -> int:
            return (await self.session.execute(
                select(func.count()).select_from(RemediationTask).where(*where, *rem_excl)
            )).scalar_one()

        succeeded = await _count_rem(
            RemediationTask.created_at >= cutoff_30d,
            RemediationTask.status == RemediationStatus.SUCCEEDED,
        )
        failed = await _count_rem(
            RemediationTask.created_at >= cutoff_30d,
            RemediationTask.status == RemediationStatus.FAILED,
        )
        total_30d = await _count_rem(RemediationTask.created_at >= cutoff_30d)
        pending = await _count_rem(RemediationTask.status == RemediationStatus.PENDING_APPROVAL)
        completed = succeeded + failed
        success_rate = round(succeeded * 100 / completed, 1) if completed else None

        action_rows = (await self.session.execute(
            select(RemediationTask.action_id, func.count())
            .where(RemediationTask.created_at >= cutoff_30d, *rem_excl)
            .group_by(RemediationTask.action_id)
            .order_by(func.count().desc())
            .limit(10)
        )).all()
        top_actions = [
            ActionStat(
                action_id=a, count=n,
                label=ACTIONS[a].label if a in ACTIONS else a,
            )
            for a, n in action_rows
        ]

        # Fleet: devices per org, with online counts.
        online_cutoff = now - ONLINE_THRESHOLD
        device_rows = (await self.session.execute(
            select(
                Device.org_id,
                func.count(),
                func.sum(
                    case((Device.last_seen_at >= online_cutoff, 1), else_=0)
                ),
            ).where(*dev_excl).group_by(Device.org_id)
        )).all()
        org_names = dict((await self.session.execute(
            select(Organization.id, Organization.name)
        )).all())
        devices_by_org = sorted(
            (
                OrgDeviceStat(
                    org_id=org_id, org_name=org_names.get(org_id, "?"),
                    devices=n, online=int(online or 0),
                )
                for org_id, n, online in device_rows
            ),
            key=lambda s: -s.devices,
        )
        total_devices = sum(s.devices for s in devices_by_org)
        online_devices = sum(s.online for s in devices_by_org)

        conversations_30d = (await self.session.execute(
            select(func.count()).select_from(Conversation).where(
                Conversation.created_at >= cutoff_30d, *conv_excl
            )
        )).scalar_one()
        # Messages carry no org_id, so scope them through their conversation.
        msg_conv_filter = [Message.conversation_id.in_(
            select(Conversation.id).where(Conversation.org_id.notin_(platform_ids))
        )] if platform_ids else []
        messages_30d = (await self.session.execute(
            select(func.count()).select_from(Message).where(
                Message.created_at >= cutoff_30d, *msg_conv_filter
            )
        )).scalar_one()

        return PlatformReports(
            signups_by_month=signups,
            remediation_total_30d=total_30d,
            remediation_succeeded_30d=succeeded,
            remediation_failed_30d=failed,
            remediation_pending=pending,
            remediation_success_rate=success_rate,
            top_actions_30d=top_actions,
            total_devices=total_devices,
            online_devices=online_devices,
            devices_by_org=devices_by_org,
            conversations_30d=conversations_30d,
            messages_30d=messages_30d,
        )

    async def audit_feed(self, *, limit: int = 100) -> list[PlatformAuditRead]:
        """What the operator did, across every org — the platform.* audit trail."""
        entries = (await self.session.execute(
            select(AuditLog)
            .where(AuditLog.action.like("platform.%"))
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )).scalars().all()
        org_names = dict((await self.session.execute(
            select(Organization.id, Organization.name)
        )).all())
        actor_ids = {e.actor_id for e in entries if e.actor_id}
        actor_emails: dict = {}
        if actor_ids:
            actor_emails = dict((await self.session.execute(
                select(User.id, User.email).where(User.id.in_(actor_ids))
            )).all())
        return [
            PlatformAuditRead(
                id=e.id, created_at=e.created_at, action=e.action,
                org_id=e.org_id, org_name=org_names.get(e.org_id),
                actor_email=actor_emails.get(e.actor_id),
                target_type=e.target_type, target_id=e.target_id, detail=e.detail,
            )
            for e in entries
        ]

    async def create_organization(
        self, *, actor: User, data: OrganizationCreate
    ) -> OrganizationAdminRead:
        """Operator provisions a new customer org + its first admin (14-day trial,
        permanent enrollment key). No auto-login — the operator shares credentials."""
        email = data.admin_email.lower()
        if await UserRepository(self.session).get_by_email(email) is not None:
            raise ConflictError("A user with that email already exists")

        org = await self.orgs.add(
            Organization(
                name=data.organization_name.strip(),
                trial_ends_at=utcnow() + timedelta(days=TRIAL_DAYS),
                agent_enrollment_key=generate_opaque_token(),
            )
        )
        admin = User(
            org_id=org.id,
            email=email,
            full_name=data.admin_name.strip(),
            hashed_password=hash_password(data.admin_password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        self.session.add(admin)
        await self.audit.record(
            org_id=org.id,
            actor_id=actor.id,
            action="platform.organization.create",
            target_type="organization",
            target_id=str(org.id),
            detail={"name": org.name, "admin_email": email},
        )
        await self.session.commit()

        try:  # welcome email is best-effort — never fail provisioning
            await EmailService().send_welcome(
                to=email, name=admin.full_name, org_name=org.name, trial_days=TRIAL_DAYS
            )
        except Exception:
            pass

        read = OrganizationAdminRead.model_validate(org)
        read.user_count = 1
        read.device_count = 0
        return read

    async def create_view_as_token(self, *, actor: User, org_id: uuid.UUID) -> ViewAsToken:
        """Mint a short-lived READ-ONLY token letting the operator view one org's
        full portal. Audited under the target org."""
        org = await self.orgs.get(org_id)
        if org is None:
            raise NotFoundError("Organization not found")
        token = create_view_as_token(admin_user_id=actor.id, org_id=org.id)
        await self.audit.record(
            org_id=org.id, actor_id=actor.id, action="platform.view_as",
            target_type="organization", target_id=str(org.id), detail={"org_name": org.name},
        )
        await self.session.commit()
        return ViewAsToken(access_token=token, org_id=org.id, org_name=org.name)

    async def get_organization(self, org_id: uuid.UUID) -> OrganizationAdminRead:
        org = await self.orgs.get(org_id)
        if org is None:
            raise NotFoundError("Organization not found")
        read = OrganizationAdminRead.model_validate(org)
        read.user_count = await self._count(User, org.id)
        read.device_count = await self._count(Device, org.id)
        return read

    async def update_organization(
        self, *, actor: User, org_id: uuid.UUID, data: OrganizationUpdate
    ) -> OrganizationAdminRead:
        org = await self.orgs.get(org_id)
        if org is None:
            raise NotFoundError("Organization not found")

        changes: dict[str, str] = {}
        if data.plan is not None:
            org.plan = data.plan
            changes["plan"] = data.plan
        if data.subscription_status is not None:
            org.subscription_status = data.subscription_status
            changes["status"] = data.subscription_status.value
        if data.trial_ends_at is not None:
            org.trial_ends_at = data.trial_ends_at
            changes["trial_ends_at"] = data.trial_ends_at.isoformat()
        if data.current_period_end is not None:
            org.current_period_end = data.current_period_end
            changes["current_period_end"] = data.current_period_end.isoformat()
        if data.extend_trial_days is not None:
            base = max(as_utc(org.trial_ends_at), utcnow()) if org.trial_ends_at else utcnow()
            org.trial_ends_at = base + timedelta(days=data.extend_trial_days)
            changes["extended_trial_days"] = str(data.extend_trial_days)
        if data.ai_pro is not None:
            org.ai_pro = data.ai_pro
            changes["ai_pro"] = str(data.ai_pro)

        await self.audit.record(
            org_id=org.id,
            actor_id=actor.id,
            action="platform.organization.update",
            target_type="organization",
            target_id=str(org.id),
            detail=changes,
        )
        await self.session.commit()

        read = OrganizationAdminRead.model_validate(org)
        read.user_count = await self._count(User, org.id)
        read.device_count = await self._count(Device, org.id)
        return read

    async def set_discount(
        self, *, actor: User, org_id: uuid.UUID, percent: int
    ) -> OrganizationAdminRead:
        org = await self.orgs.get(org_id)
        if org is None:
            raise NotFoundError("Organization not found")
        from app.services.billing import BillingService  # local import avoids a cycle
        await BillingService(self.session).apply_discount(org, percent)
        await self.audit.record(
            org_id=org.id, actor_id=actor.id, action="platform.organization.discount",
            target_type="organization", target_id=str(org.id), detail={"percent": percent},
        )
        await self.session.commit()
        return await self._read(org)

    async def clear_discount(self, *, actor: User, org_id: uuid.UUID) -> OrganizationAdminRead:
        org = await self.orgs.get(org_id)
        if org is None:
            raise NotFoundError("Organization not found")
        from app.services.billing import BillingService
        await BillingService(self.session).remove_discount(org)
        await self.audit.record(
            org_id=org.id, actor_id=actor.id, action="platform.organization.discount_removed",
            target_type="organization", target_id=str(org.id), detail={},
        )
        await self.session.commit()
        return await self._read(org)

    async def _read(self, org: Organization) -> OrganizationAdminRead:
        read = OrganizationAdminRead.model_validate(org)
        read.user_count = await self._count(User, org.id)
        read.device_count = await self._count(Device, org.id)
        return read

    async def delete_organization(self, *, actor: User, org_id: uuid.UUID) -> None:
        org = await self.orgs.get(org_id)
        if org is None:
            raise NotFoundError("Organization not found")
        name = org.name
        await self.audit.record(
            org_id=org.id,
            actor_id=actor.id,
            action="platform.organization.delete",
            target_type="organization",
            target_id=str(org.id),
            detail={"name": name},
        )
        await self.session.delete(org)
        await self.session.commit()

    async def _count(self, model, org_id: uuid.UUID) -> int:
        return (
            await self.session.execute(
                select(func.count()).select_from(model).where(model.org_id == org_id)
            )
        ).scalar_one()
