import logging
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import generate_opaque_token
from app.models import (
    AcknowledgementStatus,
    Asset,
    AssetEvent,
    AssetEventType,
    EmailSettings,
    EmailVerificationStatus,
    Organization,
    User,
)
from app.models import AssetStatus
from app.models.base import as_utc, utcnow
from app.repositories.assets import AssetRepository
from app.schemas.asset_event import AssetEventRead, AssetPassport, StatusDuration
from app.repositories.devices import DeviceRepository
from app.repositories.users import UserRepository
from app.schemas.asset import AssetCreate, AssetRead, AssetSummary, AssetUpdate
from app.services.audit import AuditService
from app.services.email import EmailService
from app.services.exceptions import ConflictError, NotFoundError

logger = logging.getLogger("astra.assets")

# Warranties expiring within this window count as "expiring soon" in the summary.
_WARRANTY_SOON_DAYS = 60


class AssetService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AssetRepository(session)
        self.users = UserRepository(session)
        self.devices = DeviceRepository(session)
        self.audit = AuditService(session)

    # -- Reads -----------------------------------------------------------------

    async def list_for_org(self, *, org_id: uuid.UUID) -> list[AssetRead]:
        assets = await self.repo.list_by_org(org_id)
        user_names, device_hosts = await self._lookup_maps(org_id)
        return [self._to_read(a, user_names, device_hosts) for a in assets]

    async def get(self, *, actor: User, asset_id: uuid.UUID) -> AssetRead:
        asset = await self._get_owned(actor.org_id, asset_id)
        user_names, device_hosts = await self._lookup_maps(actor.org_id)
        return self._to_read(asset, user_names, device_hosts)

    async def passport(self, *, actor: User, asset_id: uuid.UUID) -> AssetPassport:
        """The asset's full lifecycle history + derived analytics (time-in-status,
        current-holder-since, repair/assignment counts)."""
        asset = await self._get_owned(actor.org_id, asset_id)
        events = (await self.session.execute(
            select(AssetEvent)
            .where(AssetEvent.asset_id == asset_id)
            .order_by(AssetEvent.occurred_at.asc(), AssetEvent.created_at.asc())
        )).scalars().all()
        user_names, _ = await self._lookup_maps(actor.org_id)
        now = utcnow()

        # Status timeline → seconds spent in each status. The 'created' event carries the
        # initial status; each 'status_changed' marks a transition; the last segment runs to now.
        points: list[tuple] = []
        for e in events:
            if e.event_type in (AssetEventType.CREATED, AssetEventType.STATUS_CHANGED) and e.to_value:
                points.append((as_utc(e.occurred_at), e.to_value))
        time_in_status: dict[str, float] = {}
        for i, (ts, status) in enumerate(points):
            end = points[i + 1][0] if i + 1 < len(points) else now
            time_in_status[status] = time_in_status.get(status, 0.0) + max(0.0, (end - ts).total_seconds())

        repair_count = sum(
            1 for e in events
            if e.event_type is AssetEventType.STATUS_CHANGED and e.to_value == AssetStatus.IN_REPAIR.value
        )
        assignment_count = sum(1 for e in events if e.event_type is AssetEventType.ASSIGNED)

        current_holder = None
        holder_since = None
        if asset.assigned_to_user_id:
            current_holder = user_names.get(asset.assigned_to_user_id)
            for e in reversed(events):
                if e.event_type is AssetEventType.ASSIGNED and e.user_id == asset.assigned_to_user_id:
                    holder_since = as_utc(e.occurred_at)
                    break

        age_days = max(0, (now - as_utc(asset.created_at)).days)

        reads = [
            AssetEventRead(
                id=e.id, event_type=e.event_type,
                actor_name=user_names.get(e.actor_id) if e.actor_id else None,
                user_name=(user_names.get(e.user_id) if e.user_id else None) or e.to_value,
                from_value=e.from_value, to_value=e.to_value, note=e.note,
                occurred_at=as_utc(e.occurred_at),
            )
            for e in reversed(events)  # newest first
        ]

        return AssetPassport(
            asset_id=asset.id, name=asset.name, category=asset.category.value,
            asset_tag=asset.asset_tag, serial_number=asset.serial_number,
            current_status=asset.status.value, current_location=asset.location,
            current_holder=current_holder, holder_since=holder_since,
            acquired_at=as_utc(asset.created_at), age_days=age_days,
            repair_count=repair_count, assignment_count=assignment_count,
            time_in_status=[StatusDuration(status=s, seconds=sec) for s, sec in time_in_status.items()],
            events=reads,
        )

    async def summary(self, *, org_id: uuid.UUID) -> AssetSummary:
        assets = await self.repo.list_by_org(org_id)
        by_status: dict[str, int] = {}
        by_category: dict[str, int] = {}
        total_value = 0.0
        expiring = 0
        cutoff = date.today() + timedelta(days=_WARRANTY_SOON_DAYS)
        today = date.today()
        for a in assets:
            by_status[a.status.value] = by_status.get(a.status.value, 0) + 1
            by_category[a.category.value] = by_category.get(a.category.value, 0) + 1
            if a.purchase_cost:
                total_value += a.purchase_cost
            expiry = _parse_date(a.warranty_expiry)
            if expiry is not None and today <= expiry <= cutoff:
                expiring += 1
        return AssetSummary(
            total=len(assets),
            by_status=by_status,
            by_category=by_category,
            total_value=round(total_value, 2),
            warranty_expiring_soon=expiring,
        )

    # -- Mutations (audited) ---------------------------------------------------

    async def create(self, *, actor: User, data: AssetCreate) -> AssetRead:
        asset = Asset(org_id=actor.org_id, **data.model_dump())
        newly_assigned = False
        if asset.assigned_to_user_id is not None:
            asset.ack_token = generate_opaque_token()
            asset.acknowledgement_status = AcknowledgementStatus.PENDING
            newly_assigned = True
        asset = await self.repo.add(asset)
        self._record_event(asset, AssetEventType.CREATED, actor_id=actor.id, to_value=asset.status.value)
        if newly_assigned:
            self._record_event(
                asset, AssetEventType.ASSIGNED, actor_id=actor.id,
                to_value=await self._user_name(asset.assigned_to_user_id),
                user_id=asset.assigned_to_user_id,
            )
        await self.audit.record(
            org_id=actor.org_id,
            actor_id=actor.id,
            action="asset.create",
            target_type="asset",
            target_id=str(asset.id),
            detail={"name": asset.name, "category": asset.category.value},
        )
        await self.session.commit()
        if newly_assigned:
            await self._send_ack_email(asset)  # best-effort, after commit
        user_names, device_hosts = await self._lookup_maps(actor.org_id)
        return self._to_read(asset, user_names, device_hosts)

    async def update(
        self, *, actor: User, asset_id: uuid.UUID, data: AssetUpdate
    ) -> AssetRead:
        asset = await self._get_owned(actor.org_id, asset_id)
        previous_assignee = asset.assigned_to_user_id
        old_status = asset.status
        old_location = asset.location
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(asset, field, value)

        # Detect a (re)assignment so we can ask the new holder to acknowledge receipt.
        newly_assigned = False
        if "assigned_to_user_id" in changes:
            if asset.assigned_to_user_id is None:
                asset.acknowledgement_status = AcknowledgementStatus.NOT_REQUIRED
                asset.ack_token = None
                asset.acknowledged_at = None
            elif asset.assigned_to_user_id != previous_assignee:
                asset.ack_token = generate_opaque_token()
                asset.acknowledgement_status = AcknowledgementStatus.PENDING
                asset.acknowledged_at = None
                newly_assigned = True

        # Lifecycle events for the passport.
        if "status" in changes and asset.status != old_status:
            self._record_event(
                asset, AssetEventType.STATUS_CHANGED, actor_id=actor.id,
                from_value=old_status.value, to_value=asset.status.value,
            )
        if "location" in changes and (asset.location or None) != (old_location or None):
            self._record_event(
                asset, AssetEventType.LOCATION_CHANGED, actor_id=actor.id,
                from_value=old_location or None, to_value=asset.location or None,
            )
        if "assigned_to_user_id" in changes and asset.assigned_to_user_id != previous_assignee:
            prior_name = await self._user_name(previous_assignee)
            if asset.assigned_to_user_id is None:
                self._record_event(asset, AssetEventType.UNASSIGNED, actor_id=actor.id, from_value=prior_name)
            else:
                self._record_event(
                    asset, AssetEventType.ASSIGNED, actor_id=actor.id, from_value=prior_name,
                    to_value=await self._user_name(asset.assigned_to_user_id),
                    user_id=asset.assigned_to_user_id,
                )

        await self.audit.record(
            org_id=actor.org_id,
            actor_id=actor.id,
            action="asset.update",
            target_type="asset",
            target_id=str(asset.id),
            detail={"fields": sorted(changes.keys())},
        )
        await self.session.commit()

        if newly_assigned:
            await self._send_ack_email(asset)  # best-effort, after commit

        user_names, device_hosts = await self._lookup_maps(actor.org_id)
        return self._to_read(asset, user_names, device_hosts)

    async def resend_acknowledgement(self, *, actor: User, asset_id: uuid.UUID) -> AssetRead:
        """Re-send the receipt-confirmation email for a currently-assigned asset."""
        asset = await self._get_owned(actor.org_id, asset_id)
        if asset.assigned_to_user_id is None:
            raise ConflictError("This asset isn't assigned to anyone.")
        if not asset.ack_token:
            asset.ack_token = generate_opaque_token()
        if asset.acknowledgement_status is not AcknowledgementStatus.ACKNOWLEDGED:
            asset.acknowledgement_status = AcknowledgementStatus.PENDING
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="asset.ack_resend",
            target_type="asset", target_id=str(asset.id),
        )
        await self.session.commit()
        await self._send_ack_email(asset)
        user_names, device_hosts = await self._lookup_maps(actor.org_id)
        return self._to_read(asset, user_names, device_hosts)

    async def acknowledge_by_token(self, *, token: str) -> Asset | None:
        """Mark an asset acknowledged from its emailed link. Returns the asset (idempotent)
        or None when the token is unknown. Public — no auth, the opaque token is the proof."""
        if not token:
            return None
        asset = (await self.session.execute(
            select(Asset).where(Asset.ack_token == token)
        )).scalar_one_or_none()
        if asset is None:
            return None
        if asset.acknowledgement_status is not AcknowledgementStatus.ACKNOWLEDGED:
            asset.acknowledgement_status = AcknowledgementStatus.ACKNOWLEDGED
            asset.acknowledged_at = utcnow()
            self._record_event(
                asset, AssetEventType.ACKNOWLEDGED, actor_id=asset.assigned_to_user_id,
                to_value=await self._user_name(asset.assigned_to_user_id),
                user_id=asset.assigned_to_user_id,
            )
            await self.audit.record(
                org_id=asset.org_id, actor_id=asset.assigned_to_user_id,
                action="asset.acknowledged", target_type="asset", target_id=str(asset.id),
            )
            await self.session.commit()
        return asset

    async def _send_ack_email(self, asset: Asset) -> None:
        """Email the assignee a receipt-confirmation link, using the org's customized
        template and (when verified) sending AS the org. Never raises — an email hiccup
        must not fail the assignment."""
        try:
            email_service = EmailService()
            if not email_service.enabled or not asset.assigned_to_user_id or not asset.ack_token:
                return
            user = await self.users.get(asset.assigned_to_user_id)
            if user is None or not user.email:
                return
            org = (await self.session.execute(
                select(Organization).where(Organization.id == asset.org_id)
            )).scalar_one_or_none()
            org_name = org.name if org else "Your organization"

            # One read for both the sending identity and the custom template.
            email_row = (await self.session.execute(
                select(EmailSettings).where(EmailSettings.org_id == asset.org_id)
            )).scalar_one_or_none()
            if email_row and email_row.status is EmailVerificationStatus.VERIFIED and email_row.from_address:
                from_name, from_email = (email_row.from_name or org_name), email_row.from_address
            else:
                # Not yet verified → send from ASTRA's default, clearly on the org's behalf.
                from_name, from_email = f"{org_name} (via ASTRA)", None

            base = get_settings().public_api_url.rstrip("/")
            link = f"{base}/api/v1/assets/acknowledge?token={asset.ack_token}"
            context = await self._email_context(asset, user, org_name)
            await email_service.send_asset_assignment(
                to=user.email, context=context, ack_link=link,
                subject_tmpl=email_row.asset_email_subject if email_row else None,
                body_tmpl=email_row.asset_email_body if email_row else None,
                from_name=from_name, from_email=from_email,
            )
        except Exception:
            logger.exception("Asset acknowledgement email failed for asset %s", asset.id)

    async def _email_context(self, asset: Asset, user: User, org_name: str) -> dict[str, str]:
        """Placeholder values for the assignment email — asset fields plus, when the asset is
        linked to a device, that device's telemetry (hostname, CPU, RAM, etc.)."""
        device = await self.devices.get(asset.device_id) if asset.device_id else None
        app_count = None
        if device is not None:
            from app.repositories.telemetry import TelemetryRepository
            app_count = await TelemetryRepository(self.session).count_apps_for_device(device.id)

        def ram(mb: int | None) -> str:
            return f"{round(mb / 1024)} GB" if mb else ""

        def storage(gb: float | None) -> str:
            if not gb:
                return ""
            return f"{gb / 1024:.1f} TB" if gb >= 1024 else f"{round(gb)} GB"

        manufacturer = asset.manufacturer or (device.manufacturer if device else None)
        model = asset.model or (device.model if device else None)
        return {
            "employee_name": user.full_name,                     # "Name of user" (assignee)
            "asset_name": asset.name,
            "asset_tag": asset.asset_tag or "",
            "status": asset.status.value.replace("_", " "),
            "hostname": (device.hostname if device else "") or "",
            "brand_model": " ".join(x for x in (manufacturer, model) if x),
            "serial": asset.serial_number or (device.serial_number if device else "") or "",
            "cpu": (device.cpu_name if device else "") or "",
            "ram": ram(device.total_ram_mb) if device else "",
            "storage": storage(device.total_storage_gb) if device else "",
            "software": f"{app_count} apps" if app_count is not None else "",
            "device_user": (device.logged_in_user if device else "") or "",  # "User" on the device
            "org_name": org_name,
        }

    async def delete(self, *, actor: User, asset_id: uuid.UUID) -> None:
        asset = await self._get_owned(actor.org_id, asset_id)
        await self.repo.delete(asset)
        await self.audit.record(
            org_id=actor.org_id,
            actor_id=actor.id,
            action="asset.delete",
            target_type="asset",
            target_id=str(asset_id),
            detail={"name": asset.name},
        )
        await self.session.commit()

    # -- Helpers ---------------------------------------------------------------

    async def _get_owned(self, org_id: uuid.UUID, asset_id: uuid.UUID) -> Asset:
        asset = await self.repo.get(asset_id)
        if asset is None or asset.org_id != org_id:
            raise NotFoundError("Asset not found")
        return asset

    # -- Lifecycle events (the device passport) --------------------------------

    def _record_event(
        self, asset: Asset, event_type: AssetEventType, *, actor_id: uuid.UUID | None = None,
        from_value: str | None = None, to_value: str | None = None,
        user_id: uuid.UUID | None = None, note: str | None = None,
    ) -> None:
        self.session.add(AssetEvent(
            org_id=asset.org_id, asset_id=asset.id, event_type=event_type,
            actor_id=actor_id, user_id=user_id, from_value=from_value, to_value=to_value,
            note=note, occurred_at=utcnow(),
        ))

    async def _user_name(self, user_id: uuid.UUID | None) -> str | None:
        if user_id is None:
            return None
        user = await self.users.get(user_id)
        return user.full_name if user else None

    async def _lookup_maps(
        self, org_id: uuid.UUID
    ) -> tuple[dict[uuid.UUID, str], dict[uuid.UUID, str]]:
        user_names = {u.id: u.full_name for u in await self.users.list_by_org(org_id)}
        device_hosts = {d.id: d.hostname for d in await self.devices.list_by_org(org_id)}
        return user_names, device_hosts

    @staticmethod
    def _to_read(
        asset: Asset,
        user_names: dict[uuid.UUID, str],
        device_hosts: dict[uuid.UUID, str],
    ) -> AssetRead:
        read = AssetRead.model_validate(asset)
        if asset.assigned_to_user_id:
            read.assigned_to_name = user_names.get(asset.assigned_to_user_id)
        if asset.device_id:
            read.device_hostname = device_hosts.get(asset.device_id)
        return read


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None
