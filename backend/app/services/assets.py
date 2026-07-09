import uuid
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset, User
from app.repositories.assets import AssetRepository
from app.repositories.devices import DeviceRepository
from app.repositories.users import UserRepository
from app.schemas.asset import AssetCreate, AssetRead, AssetSummary, AssetUpdate
from app.services.audit import AuditService
from app.services.exceptions import NotFoundError

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
        user_names, device_hosts = await self._lookup_maps(actor.org_id)
        return self._to_read(asset, user_names, device_hosts)

    async def update(
        self, *, actor: User, asset_id: uuid.UUID, data: AssetUpdate
    ) -> AssetRead:
        asset = await self._get_owned(actor.org_id, asset_id)
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(asset, field, value)
        await self.audit.record(
            org_id=actor.org_id,
            actor_id=actor.id,
            action="asset.update",
            target_type="asset",
            target_id=str(asset.id),
            detail={"fields": sorted(changes.keys())},
        )
        await self.session.commit()
        user_names, device_hosts = await self._lookup_maps(actor.org_id)
        return self._to_read(asset, user_names, device_hosts)

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
