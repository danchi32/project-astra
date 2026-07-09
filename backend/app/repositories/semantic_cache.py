import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SemanticCacheEntry


class SemanticCacheRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_org(self, org_id: uuid.UUID) -> list[SemanticCacheEntry]:
        # Loads the org's entries for in-process similarity scoring. A production
        # deployment would push this into a vector index (Qdrant / pgvector).
        result = await self.session.execute(
            select(SemanticCacheEntry).where(SemanticCacheEntry.org_id == org_id)
        )
        return list(result.scalars().all())

    async def add(self, entry: SemanticCacheEntry) -> SemanticCacheEntry:
        self.session.add(entry)
        await self.session.flush()
        return entry
