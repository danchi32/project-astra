import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset


class AssetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, asset_id: uuid.UUID) -> Asset | None:
        return await self.session.get(Asset, asset_id)

    async def list_by_org(self, org_id: uuid.UUID, *, archived: bool = False) -> list[Asset]:
        """Active assets by default; pass archived=True for the archive view."""
        cond = Asset.archived_at.is_not(None) if archived else Asset.archived_at.is_(None)
        result = await self.session.execute(
            select(Asset)
            .where(Asset.org_id == org_id, cond)
            .order_by(Asset.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_page(
        self,
        org_id: uuid.UUID,
        *,
        archived: bool = False,
        q: str | None = None,
        status: str | None = None,
        location: str | None = None,
        device_id: uuid.UUID | None = None,
        device_ids: list[uuid.UUID] | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Asset], int]:
        """One page of the register. `device_id` is how a caller that wants one device's
        asset asks for it — pulling the whole register and finding it client-side turns into
        "search the first page only" the moment this is paged, and the asset panel would go
        blank for anyone past it."""
        from app.schemas.pagination import paginate

        cond = Asset.archived_at.is_not(None) if archived else Asset.archived_at.is_(None)
        stmt = select(Asset).where(Asset.org_id == org_id, cond)
        if device_id is not None:
            stmt = stmt.where(Asset.device_id == device_id)
        if status:
            stmt = stmt.where(Asset.status == status)
        if location is not None:
            # "" means the unassigned bucket, which the UI shows as its own option. Without
            # this case that filter would silently return nothing.
            stmt = stmt.where(
                Asset.location.is_(None) if location == "" else Asset.location == location
            )
        if device_ids:
            # For the devices table, which labels each row with its asset's state and
            # location. It used to fetch the whole register to label one page — 2,000 rows
            # read to annotate 50, and once the register is paged it would simply annotate
            # the wrong ones.
            stmt = stmt.where(Asset.device_id.in_(device_ids))
        if q:
            like = f"%{q.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Asset.name).like(like),
                    func.lower(Asset.asset_tag).like(like),
                    func.lower(Asset.serial_number).like(like),
                    func.lower(Asset.manufacturer).like(like),
                    func.lower(Asset.model).like(like),
                    func.lower(Asset.location).like(like),
                )
            )
        stmt = stmt.order_by(Asset.created_at.desc())
        rows, total, _, _ = await paginate(
            self.session, stmt, page=offset // max(1, limit) + 1, page_size=limit
        )
        return rows, total

    async def distinct_locations(self, org_id: uuid.UUID) -> list[str]:
        """Every location value in use, for the filter dropdown.

        Its own query because the dropdown must offer every location in the org, not the
        handful that happen to appear on the page you are looking at.
        """
        rows = (await self.session.execute(
            select(Asset.location)
            .where(Asset.org_id == org_id, Asset.archived_at.is_(None),
                   Asset.location.is_not(None), Asset.location != "")
            .distinct()
            .order_by(Asset.location)
        )).all()
        return [r[0] for r in rows]

    async def add(self, asset: Asset) -> Asset:
        self.session.add(asset)
        await self.session.flush()
        return asset

    async def delete(self, asset: Asset) -> None:
        await self.session.delete(asset)
