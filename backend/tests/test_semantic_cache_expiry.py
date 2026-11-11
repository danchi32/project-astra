"""G6 — cached AI answers expire, since their question text can name a person."""
from datetime import timedelta

from sqlalchemy import func, select

from app.models import SemanticCacheEntry
from app.models.base import utcnow
from app.repositories.semantic_cache import SemanticCacheRepository


def _entry(org_id, text, age_days=0):
    return SemanticCacheEntry(org_id=org_id, query_text=text, embedding=[0.0], embedding_model="hash",
                              answer="a", created_at=utcnow() - timedelta(days=age_days))


async def test_expired_answers_are_not_served_and_are_pruned(session_factory, org, other_org):
    async with session_factory() as s:
        s.add_all([_entry(org.id, "old: why is asha's vpn slow", 91), _entry(org.id, "fresh", 1),
                   _entry(other_org.id, "other org, old", 91)])
        await s.commit()

        repo = SemanticCacheRepository(s)
        assert [e.query_text for e in await repo.list_by_org(org.id)] == ["fresh"]

        await repo.add(_entry(org.id, "new"))
        await s.commit()
        texts = set((await s.execute(select(SemanticCacheEntry.query_text))).scalars())
        # This org's expired entry is gone; another org's is pruned on ITS next write, not this one.
        assert texts == {"fresh", "new", "other org, old"}
        assert await s.scalar(select(func.count()).select_from(SemanticCacheEntry)) == 3
