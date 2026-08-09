"""Rebuilding stored vectors after the vector space changes.

This module exists because the first version of it was a standalone script that nothing
executed until it ran against production — where it failed on its first import. It was
moved here specifically so it could be tested, and then it wasn't. These are the tests that
should have come with the move.

A backfill tool has an unusual property: the only time it runs is the moment you most need
it to work, on data you cannot easily restore. So what is pinned here is mostly what it
must not do — not lose rows, not stop silently, not claim work it didn't do.
"""
import pytest
from sqlalchemy import select

from app.models import KnowledgeArticle, LearnedAction, SemanticCacheEntry
from app.models.base import utcnow
from app.services.ai.embeddings import EmbeddingError, HashingEmbeddingProvider
from app.services.ai.knowledge import KnowledgeBaseService
from app.services.ai.reembed import reembed_all


class NewProvider:
    """A different vector space from whatever wrote the rows."""

    name = "test-v9-4"

    def __init__(self) -> None:
        self.seen: list[str] = []

    async def embed(self, text: str, *, purpose: str) -> list[float]:
        self.seen.append(text)
        return [1.0, 0.0, 0.0, 0.0]


class FailingProvider(NewProvider):
    """Succeeds `ok` times, then refuses — a rate limit part-way through a backfill."""

    def __init__(self, ok: int) -> None:
        super().__init__()
        self._ok = ok

    async def embed(self, text: str, *, purpose: str):
        if len(self.seen) >= self._ok:
            raise EmbeddingError("429 from the embedding service")
        return await super().embed(text, purpose=purpose)


async def _seed(session_factory, org_id, *, articles=1, cached=1, learned=1):
    """Rows written by the current provider — stale the moment a new one appears."""
    hashing = HashingEmbeddingProvider()
    async with session_factory() as session:
        for i in range(articles):
            svc = KnowledgeBaseService(session)
            await svc.create(org_id=org_id, title=f"Article {i}", content="Body text.")
        for i in range(cached):
            session.add(SemanticCacheEntry(
                org_id=org_id, query_text=f"question {i}",
                embedding=await hashing.embed(f"question {i}", purpose="document"),
                embedding_model=hashing.name, answer="an answer",
            ))
        for i in range(learned):
            session.add(LearnedAction(
                org_id=org_id, query_text=f"problem {i}",
                embedding=await hashing.embed(f"problem {i}", purpose="document"),
                embedding_model=hashing.name, action_id="flush_dns",
            ))
        await session.commit()


# ── The happy path, actually executed ──────────────────────────────────────


async def test_it_rebuilds_every_stale_row(session_factory, admin_user):
    await _seed(session_factory, admin_user.org_id, articles=2, cached=3, learned=1)
    provider = NewProvider()

    report = await reembed_all(session_factory, provider, dry_run=False)

    assert report.total_done == 6
    assert report.error is None
    async with session_factory() as session:
        for model in (KnowledgeArticle, SemanticCacheEntry, LearnedAction):
            rows = list((await session.execute(select(model))).scalars())
            assert rows, model.__name__
            assert all(r.embedding_model == provider.name for r in rows), model.__name__


async def test_a_dry_run_changes_nothing(session_factory, admin_user):
    """The whole point of the flag. It reports and stops — if it wrote anything, the
    'let me check first' step would itself be the risky operation."""
    await _seed(session_factory, admin_user.org_id, articles=1, cached=2, learned=1)
    provider = NewProvider()

    report = await reembed_all(session_factory, provider, dry_run=True)

    assert report.total_stale == 4
    assert report.total_done == 0
    assert provider.seen == [], "a dry run must not call the embedding provider at all"
    async with session_factory() as session:
        rows = list((await session.execute(select(SemanticCacheEntry))).scalars())
        assert all(r.embedding_model != provider.name for r in rows)


async def test_rerunning_is_a_no_op(session_factory, admin_user):
    """Safe to re-run: a second pass finds nothing, so an interrupted run resumes rather
    than redoing work already paid for."""
    await _seed(session_factory, admin_user.org_id)
    provider = NewProvider()
    await reembed_all(session_factory, provider, dry_run=False)

    again = await reembed_all(session_factory, provider, dry_run=False)
    assert again.total_stale == 0
    assert again.total_done == 0


async def test_a_knowledge_article_is_rebuilt_with_its_aliases(session_factory, admin_user):
    """The text fed back in has to match what a fresh write would embed. Rebuilding from
    title+content alone would quietly drop the user-phrasings that make the article
    findable — and nothing would report it."""
    from app.services.ai.aliases import AliasGenerator
    from app.services.ai.provider import LLMResponse

    class FakeLLM:
        async def generate(self, *, system, messages, tools):
            return LLMResponse(text='["laptop bahut slow hai"]')

    async with session_factory() as session:
        await KnowledgeBaseService(session, aliases=AliasGenerator(provider=FakeLLM())).create(
            org_id=admin_user.org_id, title="Memory", content="Check the working set.",
        )

    provider = NewProvider()
    await reembed_all(session_factory, provider, dry_run=False)

    embedded = " ".join(provider.seen)
    assert "laptop bahut slow hai" in embedded
    assert "Check the working set." in embedded


# ── Failing without losing anything ────────────────────────────────────────


async def test_it_stops_at_the_first_failure_and_keeps_what_succeeded(
    session_factory, admin_user
):
    """A refusing provider means grinding through the rest just repeats the refusal. What
    matters is that the rows already rebuilt are committed and the rest are untouched —
    the state they were in before the run."""
    await _seed(session_factory, admin_user.org_id, articles=0, cached=5, learned=0)
    provider = FailingProvider(ok=2)

    report = await reembed_all(session_factory, provider, dry_run=False)

    assert report.error is not None and "429" in report.error
    assert report.total_done == 2

    async with session_factory() as session:
        rows = list((await session.execute(select(SemanticCacheEntry))).scalars())
    moved = [r for r in rows if r.embedding_model == provider.name]
    stayed = [r for r in rows if r.embedding_model != provider.name]
    assert len(moved) == 2, "successful rows must be committed, not rolled back"
    assert len(stayed) == 3, "the rest keep their previous vectors"


async def test_a_failed_run_resumes_where_it_stopped(session_factory, admin_user):
    await _seed(session_factory, admin_user.org_id, articles=0, cached=5, learned=0)
    await reembed_all(session_factory, FailingProvider(ok=2), dry_run=False)

    report = await reembed_all(session_factory, NewProvider(), dry_run=False)
    assert report.total_done == 3
    assert report.error is None


async def test_nothing_to_do_is_reported_as_such(session_factory, admin_user):
    report = await reembed_all(session_factory, NewProvider(), dry_run=False)
    assert report.total_stale == 0
    assert any("up to date" in line for line in report.lines())


# ── What the operator reads ────────────────────────────────────────────────


async def test_the_report_says_which_provider_it_targeted(session_factory, admin_user):
    """Running a backfill onto the wrong vector space is the one mistake this tool can
    make that looks like success, so the provider name leads the output."""
    report = await reembed_all(session_factory, NewProvider(), dry_run=True)
    assert "test-v9-4" in report.lines()[0]


async def test_a_dry_run_says_it_changed_nothing(session_factory, admin_user):
    await _seed(session_factory, admin_user.org_id)
    lines = "\n".join((await reembed_all(session_factory, NewProvider(), dry_run=True)).lines())
    assert "would be re-embedded" in lines
    assert "Nothing changed" in lines


async def test_a_failed_run_says_so_instead_of_reporting_a_total(session_factory, admin_user):
    """Exit output is all an operator gets from a Cloud Run job. 'Re-embedded 2 rows' after
    a failure would read as a completed migration."""
    await _seed(session_factory, admin_user.org_id, articles=0, cached=4, learned=0)
    lines = "\n".join(
        (await reembed_all(session_factory, FailingProvider(ok=1), dry_run=False)).lines()
    )
    assert "Stopped after an embedding failure" in lines
    assert "keep their previous vectors" in lines


async def test_reembedding_produces_the_same_vector_as_writing_the_article_fresh(
    session_factory, admin_user
):
    """The one thing this module exists to guarantee.

    TARGETS used to carry its own copy of the embedding formula. When `embedding_text`
    changed, a re-embedded article was built from different text than a newly written one —
    so the job whose entire purpose is making old rows match new ones would have produced
    rows that matched neither. Nothing would have failed; search would just have been
    quietly worse for exactly the articles someone had repaired.
    """
    from app.services.ai.aliases import embedding_text
    from app.services.ai.embeddings import get_embedding_provider
    from app.services.ai.reembed import TARGETS

    provider = get_embedding_provider()
    article = KnowledgeArticle(
        org_id=admin_user.org_id,
        title="Printing does not work",
        content="Symptoms: jobs sit in the queue. " + ("Restart the spooler. " * 60),
        symptom_samples=["printer not printing", "print queue stuck"],
        embedding=[0.0], embedding_model="hash-v1-256", published_at=utcnow(),
    )

    text_of = next(fn for model, _, fn in TARGETS if model is KnowledgeArticle)
    rebuilt = await provider.embed(text_of(article), purpose="document")
    written_fresh = await provider.embed(
        embedding_text(article.title, article.content, article.symptom_samples),
        purpose="document",
    )
    assert rebuilt == written_fresh
