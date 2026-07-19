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
    EmailSettings,
    EmailVerificationStatus,
    Organization,
    User,
)
from app.models.base import utcnow
from app.repositories.assets import AssetRepository
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
            await email_service.send_asset_assignment(
                to=user.email, name=user.full_name, asset_name=asset.name,
                asset_tag=asset.asset_tag, org_name=org_name, ack_link=link,
                subject_tmpl=email_row.asset_email_subject if email_row else None,
                body_tmpl=email_row.asset_email_body if email_row else None,
                from_name=from_name, from_email=from_email,
            )
        except Exception:
            logger.exception("Asset acknowledgement email failed for asset %s", asset.id)

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
