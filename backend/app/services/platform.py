"""Platform-operator (super-admin) operations that span ALL organizations.

This is the one service that intentionally crosses org boundaries, so every
mutation is audited under the target org.
"""
import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_view_as_token, generate_opaque_token, hash_password
from app.models import (
    Device,
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
    OrganizationAdminRead,
    OrganizationCreate,
    OrganizationUpdate,
    PlatformOverview,
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

    async def list_organizations(self) -> list[OrganizationAdminRead]:
        orgs = (await self.session.execute(select(Organization).order_by(Organization.created_at))).scalars().all()
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
        """Aggregate stats across ALL organizations for the operator's landing view."""
        now = utcnow()
        total_orgs = (await self.session.execute(select(func.count()).select_from(Organization))).scalar_one()

        status_rows = (await self.session.execute(
            select(Organization.subscription_status, func.count()).group_by(Organization.subscription_status)
        )).all()
        orgs_by_status = {getattr(s, "value", s): n for s, n in status_rows}

        trials_ending = (await self.session.execute(
            select(func.count()).select_from(Organization).where(
                Organization.subscription_status == SubscriptionStatus.TRIALING,
                Organization.trial_ends_at.is_not(None),
                Organization.trial_ends_at >= now,
                Organization.trial_ends_at <= now + timedelta(days=7),
            )
        )).scalar_one()

        total_users = (await self.session.execute(select(func.count()).select_from(User))).scalar_one()
        total_devices = (await self.session.execute(select(func.count()).select_from(Device))).scalar_one()
        online = (await self.session.execute(
            select(func.count()).select_from(Device).where(
                Device.last_seen_at.is_not(None),
                Device.last_seen_at >= now - ONLINE_THRESHOLD,
            )
        )).scalar_one()
        licenses = (await self.session.execute(
            select(func.coalesce(func.sum(Organization.license_count), 0))
        )).scalar_one()
        pending = (await self.session.execute(
            select(func.count()).select_from(RemediationTask).where(
                RemediationTask.status == RemediationStatus.PENDING_APPROVAL
            )
        )).scalar_one()

        signups_30d = (await self.session.execute(
            select(func.count()).select_from(Organization).where(
                Organization.created_at >= now - timedelta(days=30)
            )
        )).scalar_one()

        # Revenue: only ACTIVE (paying) orgs contribute; apply each org's discount.
        active_rows = (await self.session.execute(
            select(Organization.license_count, Organization.discount_percent).where(
                Organization.subscription_status == SubscriptionStatus.ACTIVE
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
