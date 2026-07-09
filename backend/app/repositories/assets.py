import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset


class AssetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, asset_id: uuid.UUID) -> Asset | None:
        return await self.session.get(Asset, asset_id)

    async def list_by_org(self, org_id: uuid.UUID) -> list[Asset]:
        result = await self.session.execute(
            select(Asset)
            .where(Asset.org_id == org_id)
            .order_by(Asset.created_at.desc())
        )
        return list(result.scalars().all())

    async def add(self, asset: Asset) -> Asset:
        self.session.add(asset)
        await self.session.flush()
        return asset

    async def delete(self, asset: Asset) -> None:
        await self.session.delete(asset)
