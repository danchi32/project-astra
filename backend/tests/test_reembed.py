"""The re-embed backfill.

This exists because the first version of this tool shipped without ever being executed and
failed on its opening import when production finally ran it. The point of these tests is
not elegance — it is that the code path runs at all, on every commit, before anyone needs
it during a migration.
"""
import pytest
from sqlalchemy import select

from app.models import KnowledgeArticle, LearnedAction, SemanticCacheEntry
from app.services.ai.embeddings import EmbeddingError, HashingEmbeddingProvider
from app.services.ai.knowledge import KnowledgeBaseService
from app.services.ai.reembed import reembed_all


class NewSpace:
    """A provider claiming a different vector space from anything already stored."""

    name = "test-space-v9"

    def __init__(self, fail_after: int | None = None) -> None:
        self.calls = 0
        self.fail_after = fail_after

    async def embed(self, text: str, *, purpose: str) -> list[float]:
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise EmbeddingError("provider is down")
        return [float(len(text) % 7), 1.0, 0.0]


async def _seed(session_factory, org_id, articles: int = 3) -> None:
    async with session_factory() as session:
        svc = KnowledgeBaseService(session)
        for i in range(articles):
            await svc.create(org_id=org_id, title=f"Article {i}", content=f"Body {i}")
        session.add(SemanticCacheEntry(
            org_id=org_id, query_text="how do I reset my password",
            embedding=[0.1, 0.2], answer="Use the portal.",
            embedding_model=HashingEmbeddingProvider().name,
        ))
        session.add(LearnedAction(
            org_id=org_id, query_text="outlook is stuck", embedding=[0.3],
            action_id="restart_outlook",
            embedding_model=HashingEmbeddingProvider().name,
        ))
        await session.commit()


# ── It runs ────────────────────────────────────────────────────────────────


async def test_dry_run_counts_without_changing_anything(session_factory, admin_user):
    await _seed(session_factory, admin_user.org_id)
    provider = NewSpace()

    report = await reembed_all(session_factory, provider, dry_run=True)

    assert report.total_stale == 5           # 3 articles + 1 cache + 1 learned
    assert report.total_done == 0
    assert provider.calls == 0, "a dry run must not call the embedding provider"

    async with session_factory() as session:
        rows = (await session.execute(select(KnowledgeArticle))).scalars().all()
    assert all(r.embedding_model != provider.name for r in rows)


async def test_a_real_run_moves_every_store(session_factory, admin_user):
    await _seed(session_factory, admin_user.org_id)
    provider = NewSpace()

    report = await reembed_all(session_factory, provider, dry_run=False)
    assert report.total_done == 5
    assert report.error is None

    async with session_factory() as session:
        for model in (KnowledgeArticle, SemanticCacheEntry, LearnedAction):
            rows = (await session.execute(select(model))).scalars().all()
            assert rows and all(r.embedding_model == provider.name for r in rows), model


async def test_re_running_is_a_no_op(session_factory, admin_user):
    """Safe to re-run: the second pass finds nothing left and calls the provider zero
    times. Without this an operator repeating the command would pay for the whole corpus
    again — free on the hashing provider, not free on a hosted one."""
    await _seed(session_factory, admin_user.org_id)
    await reembed_all(session_factory, NewSpace(), dry_run=False)

    again = NewSpace()  # same name — same vector space
    report = await reembed_all(session_factory, again, dry_run=False)
    assert report.total_stale == 0
    assert again.calls == 0


async def test_articles_are_re_embedded_with_their_aliases(session_factory, admin_user):
    """The embedded text must be rebuilt the same way it was built — title, body AND the
    user phrasings. Dropping the aliases here would quietly undo the thing that makes an
    article findable, and nothing would report it."""
    captured: list[str] = []

    class Capturing(NewSpace):
        async def embed(self, text, *, purpose):
            captured.append(text)
            return await super().embed(text, purpose=purpose)

    async with session_factory() as session:
        article = await KnowledgeBaseService(session).create(
            org_id=admin_user.org_id, title="Memory", content="Check working set."
        )
        article.symptom_samples = ["mera laptop slow hai"]
        await session.commit()

    await reembed_all(session_factory, Capturing(), dry_run=False)
    assert any("mera laptop slow hai" in t for t in captured)


# ── It fails safely ────────────────────────────────────────────────────────


async def test_a_provider_failure_stops_and_keeps_the_old_vectors(session_factory, admin_user):
    """Rows that failed keep their previous vectors — the state they were already in —
    rather than being left with a broken one that nothing would ever report."""
    await _seed(session_factory, admin_user.org_id, articles=3)
    provider = NewSpace(fail_after=2)

    report = await reembed_all(session_factory, provider, dry_run=False)

    assert report.error is not None
    assert report.total_done == 2

    async with session_factory() as session:
        rows = (await session.execute(select(KnowledgeArticle))).scalars().all()
    moved = [r for r in rows if r.embedding_model == provider.name]
    stayed = [r for r in rows if r.embedding_model != provider.name]
    assert len(moved) == 2 and len(stayed) == 1
    # The one left behind still has a usable vector from its old space.
    assert stayed[0].embedding


async def test_progress_survives_a_failure_so_a_re_run_resumes(session_factory, admin_user):
    """The work already done must be committed, not rolled back — otherwise every retry
    starts from zero and a large migration can never finish through a flaky provider."""
    await _seed(session_factory, admin_user.org_id, articles=3)
    await reembed_all(session_factory, NewSpace(fail_after=2), dry_run=False)

    healthy = NewSpace()
    healthy.name = "test-space-v9"
    report = await reembed_all(session_factory, healthy, dry_run=False)
    assert report.total_stale == 3, "only the rows that failed should remain"
    assert report.error is None


# ── What it prints ─────────────────────────────────────────────────────────


async def test_the_dry_run_report_states_the_provider_and_the_counts(session_factory, admin_user):
    """This output is the entire point of a dry run — someone reads it and decides."""
    await _seed(session_factory, admin_user.org_id)
    report = await reembed_all(session_factory, NewSpace(), dry_run=True)
    text = "\n".join(report.lines())

    assert "test-space-v9" in text
    assert "knowledge articles: 3 row(s) would be re-embedded" in text
    assert "Nothing changed" in text


async def test_an_up_to_date_store_says_so(session_factory, admin_user):
    await _seed(session_factory, admin_user.org_id)
    provider = NewSpace()
    await reembed_all(session_factory, provider, dry_run=False)
    report = await reembed_all(session_factory, provider, dry_run=True)
    assert "up to date" in "\n".join(report.lines())


def test_the_cli_imports():
    """The failure that started all this: the script referenced a session factory that did
    not exist, and nothing caught it until production ran the job."""
    import importlib.util
    import pathlib

    path = pathlib.Path(__file__).parent.parent / "scripts" / "reembed.py"
    spec = importlib.util.spec_from_file_location("reembed_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)          # raises if any import is wrong
    assert callable(module.main)
