"""Articles saved while the model was unreachable, and how they get fixed.

`AliasGenerator.for_article` never raises — losing a technician's article because the LLM
was busy would be worse than losing recall. But the article is then stored with no aliases,
and retrieval is lexical: "Wi-Fi keeps dropping" tokenises to ['wi','fi',...], a user types
"wifi", and cosine similarity is exactly 0.0 — below the floor, so the search returns
nothing at all rather than something imperfect.

Nothing retried those articles and nothing counted them, so the damage was permanent and
invisible. These tests pin the three things that changed.
"""
import pytest
from sqlalchemy import select

from app.models import KnowledgeArticle, Organization
from app.services.ai.aliases import AliasGenerator
from app.services.ai.backfill_aliases import backfill
from app.services.ai.embeddings import get_embedding_provider
from app.services.ai.knowledge import KnowledgeBaseService

TITLE = "Wi-Fi keeps dropping"
BODY = "Restart the network adapter. If the problem persists, flush the DNS cache."
ALIASES = ["wifi disconnect", "wifi not working", "internet keeps cutting out"]


class _Unavailable(AliasGenerator):
    """The model is down, or no key is configured."""
    def __init__(self):
        super().__init__(provider=None)
        self._enabled = False


class _Working(AliasGenerator):
    def __init__(self, aliases=ALIASES):
        super().__init__(provider=None)
        self._enabled = True
        self._aliases = aliases

    async def for_article(self, *, title, content):
        return self._aliases


async def _org(session):
    org = Organization(name="KB Co")
    session.add(org)
    await session.flush()
    return org


async def test_unavailable_and_empty_are_stored_differently(session_factory):
    """Both used to become NULL, so nothing could tell "the model had nothing to add" from
    "we never asked" — and only the second is worth retrying."""
    async with session_factory() as s:
        org = await _org(s)
        never_asked = await KnowledgeBaseService(s, aliases=_Unavailable()).create(
            org_id=org.id, title=TITLE, content=BODY)
        asked_got_nothing = await KnowledgeBaseService(s, aliases=_Working([])).create(
            org_id=org.id, title="Printer offline", content="Restart the print spooler.")

    assert never_asked.symptom_samples is None
    assert asked_got_nothing.symptom_samples == []


async def test_an_article_saved_without_aliases_is_unfindable_by_natural_wording(session_factory):
    """The symptom this whole fix exists for. Not a weak result — no result."""
    async with session_factory() as s:
        org = await _org(s)
        kb = KnowledgeBaseService(s, aliases=_Unavailable())
        await kb.create(org_id=org.id, title=TITLE, content=BODY)
        assert await kb.search(org_id=org.id, query="wifi disconnect ho raha hai") == []


async def test_backfill_makes_it_findable_again(session_factory):
    async with session_factory() as s:
        org = await _org(s)
        await KnowledgeBaseService(s, aliases=_Unavailable()).create(
            org_id=org.id, title=TITLE, content=BODY)
        org_id = org.id
        await s.commit()

    import app.services.ai.backfill_aliases as mod
    mod.AliasGenerator = _Working                       # the model is back
    try:
        report = await backfill(session_factory, get_embedding_provider())
    finally:
        mod.AliasGenerator = AliasGenerator

    assert report.missing == 1
    assert report.filled == 1

    async with session_factory() as s:
        found = await KnowledgeBaseService(s).search(
            org_id=org_id, query="wifi disconnect ho raha hai")
    assert [a.title for a in found] == [TITLE], "backfill must restore retrieval, not just the column"


async def test_a_dry_run_writes_nothing(session_factory):
    async with session_factory() as s:
        org = await _org(s)
        await KnowledgeBaseService(s, aliases=_Unavailable()).create(
            org_id=org.id, title=TITLE, content=BODY)
        await s.commit()

    report = await backfill(session_factory, get_embedding_provider(), dry_run=True)
    assert report.missing == 1
    assert report.filled == 0

    async with session_factory() as s:
        row = (await s.execute(select(KnowledgeArticle))).scalars().one()
        assert row.symptom_samples is None


async def test_backfill_with_the_model_still_down_stops_instead_of_looping(session_factory):
    """Every article in the batch fails, so the next batch is the same rows. Without the
    progress check this is an infinite loop against a paid API."""
    async with session_factory() as s:
        org = await _org(s)
        await KnowledgeBaseService(s, aliases=_Unavailable()).create(
            org_id=org.id, title=TITLE, content=BODY)
        await s.commit()

    report = await backfill(session_factory, get_embedding_provider())
    assert report.filled == 0
    assert report.still_missing == 1

    async with session_factory() as s:
        row = (await s.execute(select(KnowledgeArticle))).scalars().one()
        assert row.symptom_samples is None, "left NULL so a later run retries it"
