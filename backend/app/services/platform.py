"""Platform-operator (super-admin) operations that span ALL organizations.

This is the one service that intentionally crosses org boundaries, so every
mutation is audited under the target org.
"""
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_view_as_token, generate_opaque_token, hash_password
from app.models import (
    OrganizationBillingProfile,
    AuditLog,
    Conversation,
    Device,
    Invoice,
    InvoiceStatus,
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
from app.schemas.public_stats import PublicStats
from app.services.remediation.actions import _ACTIONS as REMEDIATION_ACTIONS
from app.schemas.platform import (
    ActionStat,
    MonthCount,
    OrganizationAdminRead,
    OrganizationCreate,
    OrganizationUpdate,
    OrgDeviceStat,
    OrgHealthRow,
    PlatformAnalytics,
    PlatformAuditRead,
    PlatformBilling,
    PlatformBillingRow,
    PlatformOverview,
    PlatformReports,
    ProviderStat,
    RevenueMonth,
    ViewAsToken,
)
from app.services.audit import AuditService
from app.services.email import EmailService
from app.services.exceptions import ConflictError
from app.services.subscription import TRIAL_DAYS
from app.services.exceptions import NotFoundError


def _with_entitlements(org) -> OrganizationAdminRead:
    """Attach the tier and the features it grants.

    Resolved on read rather than stored so the console always shows what the server would
    actually enforce — a console that disagrees with the gate is worse than no console.
    """
    from app.services.entitlements import features_for, normalise_plan

    read = OrganizationAdminRead.model_validate(org)
    read.plan_tier = normalise_plan(org.plan)
    read.entitlements = sorted(features_for(org.plan, org.entitlement_overrides))
    read.entitlement_overrides = org.entitlement_overrides or None
    return read


def _recent_months(now, count: int) -> list[str]:
    """The last `count` calendar months as "YYYY-MM", oldest first, including this one."""
    months: list[str] = []
    y, m = now.year, now.month
    for _ in range(count):
        months.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    months.reverse()
    return months


def _month_start(month: str) -> date:
    y, m = month.split("-")
    return date(int(y), int(m), 1)


def _coerce_dt(value):
    """Normalise a timestamp to an aware UTC datetime.

    `func.max()` over a DateTime column bypasses SQLAlchemy's result processing on SQLite,
    which hands back a string where PostgreSQL hands back a datetime. Both reach this.
    """
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    return as_utc(value)


def _latest(*values):
    """The most recent of several optional timestamps, or None if there are none."""
    present = [v for v in values if v is not None]
    return max(present) if present else None


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

    _ORG_SORTS = {
        "name": Organization.name,
        "created_at": Organization.created_at,
        "plan": Organization.plan,
        "subscription_status": Organization.subscription_status,
        "updated_at": Organization.updated_at,
    }

    async def list_organizations_page(
        self,
        *,
        q: str | None = None,
        plan: str | None = None,
        subscription_status=None,
        country: str | None = None,
        sort: str = "created_at",
        desc: bool = True,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[OrganizationAdminRead], int, int, int]:
        """One page of organizations, searched and sorted in the database.

        The counts are the part worth noticing: they are fetched for the PAGE, not for the
        whole table. `list_organizations` below aggregates every user and every device in the
        system to label its rows, which is exactly the pattern that stops working somewhere
        between a demo and a real customer list.
        """
        from app.schemas.pagination import paginate

        platform_ids = await self._platform_org_ids()
        stmt = select(Organization)
        if platform_ids:
            # The operator's own internal org is not a customer and never appears here.
            stmt = stmt.where(Organization.id.not_in(platform_ids))
        if q:
            like = f"%{q.lower()}%"
            stmt = stmt.where(or_(
                func.lower(Organization.name).like(like),
                func.lower(Organization.email_domain).like(like),
            ))
        if plan:
            stmt = stmt.where(Organization.plan == plan)
        if subscription_status is not None:
            stmt = stmt.where(Organization.subscription_status == subscription_status)
        if country:
            # Country lives on the billing profile, so this is a scoped subquery rather than
            # a join — the org row itself has no address.
            stmt = stmt.where(Organization.id.in_(
                select(OrganizationBillingProfile.org_id).where(
                    OrganizationBillingProfile.country_code == country
                )
            ))

        column = self._ORG_SORTS.get(sort, Organization.created_at)
        stmt = stmt.order_by(column.desc() if desc else column.asc())

        orgs, total, page, page_size = await paginate(
            self.session, stmt, page=page, page_size=page_size
        )
        ids = [o.id for o in orgs]
        user_counts = dict((await self.session.execute(
            select(User.org_id, func.count()).where(User.org_id.in_(ids)).group_by(User.org_id)
        )).all()) if ids else {}
        device_counts = dict((await self.session.execute(
            select(Device.org_id, func.count()).where(Device.org_id.in_(ids)).group_by(Device.org_id)
        )).all()) if ids else {}

        items = []
        for org in orgs:
            read = _with_entitlements(org)
            read.user_count = user_counts.get(org.id, 0)
            read.device_count = device_counts.get(org.id, 0)
            items.append(read)
        return items, total, page, page_size

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
            read = _with_entitlements(org)
            read.user_count = user_counts.get(org.id, 0)
            read.device_count = device_counts.get(org.id, 0)
            result.append(read)
        return result

    async def public_stats(self) -> PublicStats:
        """Aggregate counts for the public marketing site.

        Lives here because this class owns `_platform_org_ids`, the rule that separates
        customers from the operator's own workspace. Getting that wrong would put our own
        test organisation on the homepage as a customer.

        Deliberately narrower than `overview()`: counts only, and only the four a visitor
        could sensibly be shown. No revenue, no trial expiry, no per-status breakdown —
        this response is served to anyone who asks, so it carries the minimum that makes
        the homepage true rather than everything that happens to be countable.
        """
        now = utcnow()
        platform_ids = await self._platform_org_ids()
        org_excl = [Organization.id.notin_(platform_ids)] if platform_ids else []
        dev_excl = [Device.org_id.notin_(platform_ids)] if platform_ids else []
        rem_excl = [RemediationTask.org_id.notin_(platform_ids)] if platform_ids else []

        organizations = (await self.session.execute(
            select(func.count()).select_from(Organization).where(*org_excl)
        )).scalar_one()
        devices = (await self.session.execute(
            select(func.count()).select_from(Device).where(*dev_excl)
        )).scalar_one()
        devices_online = (await self.session.execute(
            select(func.count()).select_from(Device).where(
                Device.last_seen_at.is_not(None),
                Device.last_seen_at >= now - ONLINE_THRESHOLD,
                *dev_excl,
            )
        )).scalar_one()
        remediations = (await self.session.execute(
            select(func.count()).select_from(RemediationTask).where(
                RemediationTask.status == RemediationStatus.SUCCEEDED, *rem_excl
            )
        )).scalar_one()

        return PublicStats(
            organizations=organizations,
            devices=devices,
            devices_online=devices_online,
            remediations=remediations,
            # From the registry, not a constant. A count typed into a page is stale the
            # first time the registry changes and nobody notices for weeks.
            remediation_actions=len(REMEDIATION_ACTIONS),
            generated_at=now,
        )

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

    # Health weights. Connectivity and engagement carry the most because a fleet that
    # quietly stopped reporting is the earliest visible form of a customer leaving — it
    # shows up months before the subscription status does.
    _W_CONNECTIVITY = 35
    _W_ENGAGEMENT = 25
    _W_ADOPTION = 20
    _W_RELIABILITY = 20

    #: Beyond this many days with no telemetry, no conversation and no audit entry, an
    #: account scores zero for engagement.
    _QUIET_LIMIT_DAYS = 30

    async def analytics(self) -> PlatformAnalytics:
        """Revenue history and per-customer health.

        `overview()` answers "what is true right now". This answers "where is this going",
        which needs invoices rather than a live seat count, and per-org scoring rather than
        platform totals.

        Every per-org figure is fetched with ONE grouped query per metric, so the cost is
        flat in the number of customers rather than one round trip each.
        """
        from app.services.entitlements import normalise_plan  # local: avoids an import cycle

        now = utcnow()
        cutoff_30d = now - timedelta(days=30)
        platform_ids = await self._platform_org_ids()

        orgs = [
            o for o in (await self.session.execute(
                select(Organization).order_by(Organization.created_at)
            )).scalars().all()
            if o.id not in platform_ids
        ]
        org_ids = [o.id for o in orgs]

        # ---- per-org aggregates (one grouped query each) -------------------------------
        online_cutoff = now - ONLINE_THRESHOLD
        devices_by_org: dict[uuid.UUID, tuple[int, int, object]] = {}
        users_by_org: dict[uuid.UUID, int] = {}
        rem_by_org: dict[uuid.UUID, tuple[int, int]] = {}
        last_conv: dict[uuid.UUID, object] = {}
        last_audit: dict[uuid.UUID, object] = {}

        if org_ids:
            devices_by_org = {
                r[0]: (r[1], int(r[2] or 0), r[3])
                for r in (await self.session.execute(
                    select(
                        Device.org_id,
                        func.count(),
                        func.sum(case((Device.last_seen_at >= online_cutoff, 1), else_=0)),
                        func.max(Device.last_seen_at),
                    ).where(Device.org_id.in_(org_ids)).group_by(Device.org_id)
                )).all()
            }
            users_by_org = dict((await self.session.execute(
                select(User.org_id, func.count())
                .where(User.org_id.in_(org_ids)).group_by(User.org_id)
            )).all())
            rem_by_org = {
                r[0]: (r[1], int(r[2] or 0))
                for r in (await self.session.execute(
                    select(
                        RemediationTask.org_id,
                        func.count(),
                        func.sum(case((RemediationTask.status == RemediationStatus.FAILED, 1), else_=0)),
                    )
                    .where(
                        RemediationTask.org_id.in_(org_ids),
                        RemediationTask.created_at >= cutoff_30d,
                    )
                    .group_by(RemediationTask.org_id)
                )).all()
            }
            last_conv = dict((await self.session.execute(
                select(Conversation.org_id, func.max(Conversation.created_at))
                .where(Conversation.org_id.in_(org_ids)).group_by(Conversation.org_id)
            )).all())
            last_audit = dict((await self.session.execute(
                select(AuditLog.org_id, func.max(AuditLog.created_at))
                .where(AuditLog.org_id.in_(org_ids)).group_by(AuditLog.org_id)
            )).all())

        # ---- revenue -------------------------------------------------------------------
        (
            revenue_currency, other_currencies, revenue_by_month,
            collected_90d, outstanding,
        ) = await self._revenue(org_ids, now)

        # ---- commercial ratios ---------------------------------------------------------
        price = get_settings().price_per_seat_cents
        paying = {
            SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE, SubscriptionStatus.SUSPENDED,
        }
        active = [o for o in orgs if o.subscription_status == SubscriptionStatus.ACTIVE]
        canceled = [o for o in orgs if o.subscription_status == SubscriptionStatus.CANCELED]

        total_mrr = 0
        if price is not None:
            total_mrr = sum(
                round((o.license_count or 0) * price * (100 - (o.discount_percent or 0)) / 100)
                for o in active
            )
        arpa_cents = round(total_mrr / len(active)) if (price is not None and active) else None

        # Only trials that have actually run out can be said to have converted or not —
        # counting trials still in flight as failures would understate the rate every day.
        finished_trials = [
            o for o in orgs
            if o.trial_ends_at is not None and as_utc(o.trial_ends_at) < now
        ]
        converted = [o for o in finished_trials if o.subscription_status in paying]
        trial_conversion_rate = (
            round(len(converted) * 100 / len(finished_trials), 1) if finished_trials else None
        )

        ever_paying = len(canceled) + len([o for o in orgs if o.subscription_status in paying])
        churn_rate = round(len(canceled) * 100 / ever_paying, 1) if ever_paying else None

        # ---- per-customer health -------------------------------------------------------
        rows: list[OrgHealthRow] = []
        for org in orgs:
            devices, online, last_seen = devices_by_org.get(org.id, (0, 0, None))
            rem_total, rem_failed = rem_by_org.get(org.id, (0, 0))
            last_activity = _latest(
                _coerce_dt(last_seen),
                _coerce_dt(last_conv.get(org.id)),
                _coerce_dt(last_audit.get(org.id)),
            )
            days_quiet = (now - last_activity).days if last_activity else None
            licenses = org.license_count or 0
            online_pct = round(online * 100 / devices, 1) if devices else None
            seat_utilisation = round(devices / licenses, 3) if licenses else None
            trial_days_left = (
                max(0, (as_utc(org.trial_ends_at) - now).days)
                if org.trial_ends_at and org.subscription_status == SubscriptionStatus.TRIALING
                else None
            )
            mrr = (
                round(licenses * price * (100 - (org.discount_percent or 0)) / 100)
                if price is not None and org.subscription_status == SubscriptionStatus.ACTIVE
                else (0 if price is not None else None)
            )

            score, band, reasons = self._score(
                status=org.subscription_status,
                devices=devices, online_pct=online_pct, days_quiet=days_quiet,
                licenses=licenses, seat_utilisation=seat_utilisation,
                rem_total=rem_total, rem_failed=rem_failed,
                trial_days_left=trial_days_left,
            )

            rows.append(OrgHealthRow(
                org_id=org.id, org_name=org.name, plan=org.plan,
                plan_tier=normalise_plan(org.plan),
                subscription_status=org.subscription_status,
                licenses=licenses, users=users_by_org.get(org.id, 0),
                devices=devices, online_devices=online, online_pct=online_pct,
                seat_utilisation=seat_utilisation,
                last_activity_at=last_activity, days_quiet=days_quiet,
                remediation_total_30d=rem_total, remediation_failed_30d=rem_failed,
                mrr_cents=mrr, trial_days_left=trial_days_left,
                health_score=score, health_band=band, risk_reasons=reasons,
            ))

        # Worst first: this table exists to be acted on from the top down.
        rows.sort(key=lambda r: (r.health_score, -(r.mrr_cents or 0)))
        health_counts: dict[str, int] = {"healthy": 0, "watch": 0, "at_risk": 0}
        for r in rows:
            health_counts[r.health_band] += 1

        return PlatformAnalytics(
            revenue_currency=revenue_currency,
            other_currencies=other_currencies,
            revenue_by_month=revenue_by_month,
            collected_90d_cents=collected_90d,
            outstanding_cents=outstanding,
            arpa_cents=arpa_cents,
            trial_conversion_rate=trial_conversion_rate,
            churn_rate=churn_rate,
            canceled_orgs=len(canceled),
            org_health=rows,
            health_counts=health_counts,
        )

    async def _revenue(
        self, org_ids: list[uuid.UUID], now
    ) -> tuple[str | None, list[str], list[RevenueMonth], int, int]:
        """Twelve months of invoiced-vs-collected, in a single currency.

        ASTRA bills on Razorpay (INR) and Paddle (USD). Adding paise to cents produces a
        number that looks like money and is not, so the trend covers whichever currency
        carries the most invoices and names the rest rather than folding them in.
        """
        months = _recent_months(now, 12)
        empty = [RevenueMonth(month=m, invoiced_cents=0, collected_cents=0, invoice_count=0)
                 for m in months]
        if not org_ids:
            return None, [], empty, 0, 0

        # Which currency the trend is denominated in — decided by invoice volume.
        currency_rows = (await self.session.execute(
            select(Invoice.currency, func.count())
            .where(Invoice.org_id.in_(org_ids))
            .group_by(Invoice.currency)
            .order_by(func.count().desc())
        )).all()
        if not currency_rows:
            return None, [], empty, 0, 0
        currency = currency_rows[0][0]
        others = sorted(c for c, _ in currency_rows[1:])

        # Bounded window: an invoice issued before it can only matter here if it was paid
        # inside it, and a 90-day grace covers that comfortably.
        window_start = _month_start(months[0])
        rows = (await self.session.execute(
            select(Invoice.issued_on, Invoice.paid_at, Invoice.status, Invoice.total_cents)
            .where(
                Invoice.org_id.in_(org_ids),
                Invoice.currency == currency,
                Invoice.issued_on >= window_start - timedelta(days=90),
            )
        )).all()

        buckets = {m: {"invoiced": 0, "collected": 0, "count": 0} for m in months}
        countable = {InvoiceStatus.OPEN, InvoiceStatus.PAID, InvoiceStatus.FAILED,
                     InvoiceStatus.REFUNDED}
        for issued_on, paid_at, status, total in rows:
            if status in countable:
                key = f"{issued_on.year:04d}-{issued_on.month:02d}"
                if key in buckets:
                    buckets[key]["invoiced"] += total or 0
                    buckets[key]["count"] += 1
            if status == InvoiceStatus.PAID and paid_at is not None:
                paid = _coerce_dt(paid_at)
                key = f"{paid.year:04d}-{paid.month:02d}"
                if key in buckets:
                    buckets[key]["collected"] += total or 0

        by_month = [
            RevenueMonth(
                month=m, invoiced_cents=buckets[m]["invoiced"],
                collected_cents=buckets[m]["collected"], invoice_count=buckets[m]["count"],
            )
            for m in months
        ]
        collected_90d = sum(b.collected_cents for b in by_month[-3:])

        outstanding = (await self.session.execute(
            select(func.coalesce(func.sum(Invoice.total_cents), 0)).where(
                Invoice.org_id.in_(org_ids),
                Invoice.currency == currency,
                Invoice.status == InvoiceStatus.OPEN,
            )
        )).scalar_one()

        return currency, others, by_month, collected_90d, int(outstanding)

    def _score(
        self, *, status, devices: int, online_pct: float | None, days_quiet: int | None,
        licenses: int, seat_utilisation: float | None, rem_total: int, rem_failed: int,
        trial_days_left: int | None,
    ) -> tuple[int, str, list[str]]:
        """Score one customer 0-100 and say, in plain words, what is wrong.

        Scoring lives here rather than in the portal because it is a commercial judgement
        the platform makes, and two clients disagreeing about who is at risk is worse than
        either answer alone.
        """
        reasons: list[str] = []

        # Connectivity — are the devices they bought actually reporting in?
        if devices == 0:
            connectivity = 0.0
            reasons.append("No devices enrolled")
        else:
            connectivity = self._W_CONNECTIVITY * (online_pct or 0) / 100
            if (online_pct or 0) < 50:
                reasons.append(f"Only {online_pct:g}% of {devices} devices online")

        # Engagement — is anyone using it?
        if days_quiet is None:
            engagement = 0.0
            reasons.append("No recorded activity")
        else:
            engagement = self._W_ENGAGEMENT * max(
                0.0, 1 - days_quiet / self._QUIET_LIMIT_DAYS
            )
            if days_quiet >= 7:
                reasons.append(f"Quiet for {days_quiet} days")

        # Adoption — did they deploy what they paid for? With no licenses sold there is
        # nothing promised, so this dimension cannot be failed.
        if licenses == 0 or seat_utilisation is None:
            adoption = float(self._W_ADOPTION)
        else:
            adoption = self._W_ADOPTION * min(1.0, seat_utilisation)
            if seat_utilisation < 0.5:
                reasons.append(f"{devices} of {licenses} licensed seats deployed")

        # Reliability — is the product working for them? Nothing attempted is not a fault.
        if rem_total == 0:
            reliability = float(self._W_RELIABILITY)
        else:
            reliability = self._W_RELIABILITY * (rem_total - rem_failed) / rem_total
            fail_pct = round(rem_failed * 100 / rem_total)
            if fail_pct >= 25:
                reasons.append(f"{fail_pct}% of fixes failed in the last 30 days")

        score = round(connectivity + engagement + adoption + reliability)

        # Billing trouble is not a score input — it is a fact that overrides the score.
        # A perfectly healthy fleet that stopped paying is still an at-risk account.
        forced = False
        if status == SubscriptionStatus.PAST_DUE:
            reasons.insert(0, "Payment past due")
            forced = True
        elif status == SubscriptionStatus.SUSPENDED:
            reasons.insert(0, "Account suspended")
            forced = True
        elif status == SubscriptionStatus.CANCELED:
            reasons.insert(0, "Subscription canceled")
            forced = True
        elif trial_days_left is not None and trial_days_left <= 7:
            reasons.insert(0, f"Trial ends in {trial_days_left} day{'' if trial_days_left == 1 else 's'}")

        if forced:
            band = "at_risk"
        elif score >= 75:
            band = "healthy"
        elif score >= 50:
            band = "watch"
        else:
            band = "at_risk"
        return score, band, reasons

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

        read = _with_entitlements(org)
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
        read = _with_entitlements(org)
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
        if data.entitlement_overrides is not None:
            # Recorded in the audit trail like every other operator action — an override is
            # a commercial decision about one account, and "who granted this and when" has
            # to be answerable later.
            org.entitlement_overrides = data.entitlement_overrides or None
            changes["entitlement_overrides"] = str(data.entitlement_overrides or {})

        await self.audit.record(
            org_id=org.id,
            actor_id=actor.id,
            action="platform.organization.update",
            target_type="organization",
            target_id=str(org.id),
            detail=changes,
        )
        await self.session.commit()

        read = _with_entitlements(org)
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
        read = _with_entitlements(org)
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
