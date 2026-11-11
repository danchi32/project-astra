import uuid
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import SemanticCacheEntry
from app.models.base import utcnow


def _cutoff():
    return utcnow() - timedelta(days=get_settings().semantic_cache_retention_days)


class SemanticCacheRepository:
    """Cached answers expire: the question text can name a person or their problem, and the
    entry isn't linked to anyone, so a per-person erase can't find it (Record of Processing,
    G6). Expired rows are never served and are deleted on the org's next write."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_org(self, org_id: uuid.UUID) -> list[SemanticCacheEntry]:
        # Loads the org's entries for in-process similarity scoring. A production
        # deployment would push this into a vector index (Qdrant / pgvector).
        result = await self.session.execute(
            select(SemanticCacheEntry).where(
                SemanticCacheEntry.org_id == org_id, SemanticCacheEntry.created_at >= _cutoff())
        )
        return list(result.scalars().all())

    async def add(self, entry: SemanticCacheEntry) -> SemanticCacheEntry:
        await self.session.execute(delete(SemanticCacheEntry).where(
            SemanticCacheEntry.org_id == entry.org_id, SemanticCacheEntry.created_at < _cutoff()))
        self.session.add(entry)
        await self.session.flush()
        return entry
