import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import SemanticCacheEntry
from app.repositories.semantic_cache import SemanticCacheRepository
from app.services.ai.embeddings import EmbeddingProvider, cosine_similarity, get_embedding_provider


class SemanticCache:
    def __init__(self, session: AsyncSession, provider: EmbeddingProvider | None = None) -> None:
        self.session = session
        self.repo = SemanticCacheRepository(session)
        self.embed = provider or get_embedding_provider()
        self.threshold = get_settings().ai_cache_similarity_threshold

    async def lookup(self, *, org_id: uuid.UUID, query: str) -> str | None:
        """Return a cached answer for a sufficiently-similar prior query, else None.
        On a hit the entry's hit counter is bumped (caller commits)."""
        query_vec = await self.embed.embed(query, purpose="query")
        best: SemanticCacheEntry | None = None
        best_sim = -1.0
        for entry in await self.repo.list_by_org(org_id):
            # Entries written by a previous provider live in a different vector
            # space; scoring them would compare numbers that mean different
            # things. They stay in the table until re-embedded — a stale cache
            # entry only costs one extra LLM call, so this needs no backfill to
            # be correct.
            if entry.embedding_model != self.embed.name:
                continue
            sim = cosine_similarity(query_vec, entry.embedding)
            if sim > best_sim:
                best_sim, best = sim, entry
        if best is not None and best_sim >= self.threshold:
            best.hit_count += 1
            await self.session.flush()
            return best.answer
        return None

    async def store(self, *, org_id: uuid.UUID, query: str, answer: str) -> None:
        query_vec = await self.embed.embed(query, purpose="document")
        await self.repo.add(
            SemanticCacheEntry(
                org_id=org_id,
                query_text=query[:1000],
                embedding=query_vec,
                embedding_model=self.embed.name,
                answer=answer[:10000],
            )
        )
