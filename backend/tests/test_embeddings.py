"""Embedding providers, and the vector-space boundary between them.

The whole reason this module exists is one failure mode. `cosine_similarity` returns 0.0
when two vectors have different lengths — not an error, not a warning. So the day someone
sets a real embedding key, every article written under the old provider would score 0.0
against every query, and the knowledge base would look empty rather than broken. Most of
what is pinned here is that this cannot happen quietly.
"""
import json

import httpx
import pytest

from app.models import KnowledgeArticle, KnowledgeSource
from app.services.ai.embeddings import (
    EmbeddingError,
    HashingEmbeddingProvider,
    VoyageEmbeddingProvider,
    cosine_similarity,
    embed_many,
)
from app.services.ai.knowledge import KnowledgeBaseService


class FakeProvider:
    """A second vector space, deliberately a different width from the hashing default."""

    def __init__(self, name: str = "fake-8", dim: int = 8) -> None:
        self.name = name
        self.dim = dim

    async def embed(self, text: str, *, purpose: str) -> list[float]:
        self.last_purpose = purpose
        vec = [0.0] * self.dim
        for i, ch in enumerate(text.lower()):
            vec[(ord(ch) + i) % self.dim] += 1.0
        norm = sum(v * v for v in vec) ** 0.5
        return [v / norm for v in vec] if norm else vec


# ── The boundary ───────────────────────────────────────────────────────────


def test_a_dimension_mismatch_scores_zero_rather_than_raising():
    """Pinning the trap itself. This is why callers must filter by model first —
    similarity will never tell them the comparison was meaningless."""
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0


async def test_switching_provider_does_not_silently_empty_the_knowledge_base(
    session_factory, admin_user, caplog
):
    """The migration-day scenario, end to end.

    An article written under the hashing provider must not be scored against a query
    embedded by a different one. It is skipped — and the skip is reported, because
    "0 results" and "your articles are on the wrong model" look identical on screen.
    """
    async with session_factory() as session:
        await KnowledgeBaseService(session).create(
            org_id=admin_user.org_id,
            title="Connecting to the VPN",
            content="Open GlobalConnect and authenticate with MFA.",
        )

    async with session_factory() as session:
        svc = KnowledgeBaseService(session, provider=FakeProvider())
        with caplog.at_level("WARNING"):
            hits = await svc.search(org_id=admin_user.org_id, query="connecting to the VPN")

    assert hits == [], "an article from another vector space must not be scored"
    assert "different model" in caplog.text
    assert "reembed" in caplog.text, "the warning has to say how to fix it"


async def test_after_re_embedding_the_article_is_found_again(session_factory, admin_user):
    """The other half: the data was never lost, only unreadable by the new provider."""
    fake = FakeProvider()

    async with session_factory() as session:
        await KnowledgeBaseService(session).create(
            org_id=admin_user.org_id, title="Connecting to the VPN",
            content="Open GlobalConnect and authenticate with MFA.",
        )

    # What scripts/reembed.py does to each stale row.
    async with session_factory() as session:
        from sqlalchemy import select

        article = (await session.execute(select(KnowledgeArticle))).scalars().first()
        article.embedding = await fake.embed(
            f"{article.title}\n{article.content}", purpose="document"
        )
        article.embedding_model = fake.name
        await session.commit()

    async with session_factory() as session:
        hits = await KnowledgeBaseService(session, provider=fake).search(
            org_id=admin_user.org_id, query="Connecting to the VPN"
        )
    assert [a.title for a in hits] == ["Connecting to the VPN"]


async def test_every_written_vector_records_its_provider(session_factory, admin_user):
    """A row without this stamp is a row a future provider switch can't reason about."""
    fake = FakeProvider()
    async with session_factory() as session:
        svc = KnowledgeBaseService(session, provider=fake)
        article = await svc.create(
            org_id=admin_user.org_id, title="T", content="C",
        )
        assert article.embedding_model == fake.name

        learned = await svc.learn_from_fix(
            org_id=admin_user.org_id, action_id="restart_outlook",
            action_label="Restart Outlook", params=None,
            symptom="outlook is stuck", success=True,
        )
        await session.commit()
        assert learned.embedding_model == fake.name


async def test_a_learned_article_updated_under_a_new_provider_moves_with_it(
    session_factory, admin_user
):
    """Learning rewrites the vector on every confirmation. That rewrite must also move the
    stamp, or the row would claim an old model while holding a new vector — the one state
    the filter cannot detect."""
    async with session_factory() as session:
        await KnowledgeBaseService(session).learn_from_fix(
            org_id=admin_user.org_id, action_id="flush_dns", action_label="Flush DNS",
            params=None, symptom="no internet", success=True,
        )
        await session.commit()

    fake = FakeProvider()
    async with session_factory() as session:
        updated = await KnowledgeBaseService(session, provider=fake).learn_from_fix(
            org_id=admin_user.org_id, action_id="flush_dns", action_label="Flush DNS",
            params=None, symptom="dns broken again", success=True,
        )
        await session.commit()

    assert updated.embedding_model == fake.name
    assert len(updated.embedding) == fake.dim


# ── Indexing vs searching ──────────────────────────────────────────────────


async def test_documents_and_queries_are_embedded_differently(session_factory, admin_user):
    """Retrieval models are asymmetric — a document is embedded to be found, a query to
    find. Sending "document" for both is a silent accuracy loss, so the call sites have to
    say which they mean."""
    fake = FakeProvider()
    async with session_factory() as session:
        svc = KnowledgeBaseService(session, provider=fake)
        await svc.create(org_id=admin_user.org_id, title="T", content="C")
        assert fake.last_purpose == "document"
        await svc.search(org_id=admin_user.org_id, query="anything")
        assert fake.last_purpose == "query"


async def test_purpose_is_not_optional():
    """A default would let a call site forget, and forgetting costs accuracy with no
    symptom. Better a TypeError at import-test time."""
    with pytest.raises(TypeError):
        await HashingEmbeddingProvider().embed("x")


# ── The offline default ────────────────────────────────────────────────────


async def test_the_hashing_provider_names_its_dimension_and_version():
    """The name is the vector space's identity. Width matters — two hashing providers of
    different widths aren't interchangeable — and so does the tokenizer version, since
    stemming changes the vectors for identical text."""
    assert HashingEmbeddingProvider().name == "hash-v3-256"
    assert HashingEmbeddingProvider(dim=64).name == "hash-v3-64"


async def test_the_hashing_provider_still_matches_on_shared_words():
    """Its documented ceiling: word overlap, not meaning. Worth pinning so a change that
    breaks even this is visible."""
    p = HashingEmbeddingProvider()
    a = await p.embed("printer is not printing", purpose="document")
    b = await p.embed("the printer will not print", purpose="query")
    c = await p.embed("outlook calendar sync", purpose="query")
    assert cosine_similarity(a, b) > cosine_similarity(a, c)


# ── The hosted provider ────────────────────────────────────────────────────


async def test_voyage_reads_the_documented_response_shape(monkeypatch):
    """`data[].embedding`, not a bare `embeddings` list. Getting this wrong would make
    every call raise on a perfectly good response."""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read().decode()
        captured["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json={
            "object": "list",
            "data": [{"object": "embedding", "embedding": [0.1, 0.2, 0.3], "index": 0}],
            "model": "voyage-4-lite",
            "usage": {"total_tokens": 8},
        })

    _install(monkeypatch, handler)
    vec = await VoyageEmbeddingProvider("key-123", "voyage-4-lite").embed(
        "hello", purpose="query"
    )
    assert vec == [0.1, 0.2, 0.3]
    assert captured["auth"] == "Bearer key-123"
    body = json.loads(captured["body"])
    assert body["input_type"] == "query"
    assert body["model"] == "voyage-4-lite"
    # A list, not a bare string: the endpoint returns data[] either way, and keeping the
    # request shape uniform means the response parsing has one case to handle.
    assert body["input"] == ["hello"]


async def test_voyage_sorts_by_index(monkeypatch):
    """The API returns an `index` on every row precisely because order isn't promised —
    trusting arrival order would occasionally return the wrong vector."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [
            {"embedding": [9.0], "index": 1},
            {"embedding": [1.0], "index": 0},
        ]})

    _install(monkeypatch, handler)
    vec = await VoyageEmbeddingProvider("k", "voyage-4-lite").embed("x", purpose="query")
    assert vec == [1.0]


@pytest.mark.parametrize("handler", [
    lambda request: httpx.Response(429, json={"detail": "rate limited"}),
    lambda request: httpx.Response(200, json={"data": []}),
    lambda request: httpx.Response(200, text="not json"),
    # A row that arrives with an empty vector. Storing that would be worse than an error:
    # the row looks embedded and is permanently unfindable.
    lambda request: httpx.Response(200, json={"data": [{"embedding": [], "index": 0}]}),
])
async def test_voyage_failures_raise_rather_than_returning_a_bad_vector(monkeypatch, handler):
    """Never return a placeholder vector on failure. A stored row with a junk embedding is
    unfindable forever and nothing ever reports it; a raised error stops at the request."""
    _install(monkeypatch, handler)
    with pytest.raises(EmbeddingError):
        await VoyageEmbeddingProvider("k", "voyage-4-lite").embed("x", purpose="document")


async def test_the_model_id_is_part_of_the_vector_space_name():
    """Two Voyage models are two vector spaces. If the name didn't carry the model, a model
    change would look like no change at all and the filter would compare across them."""
    assert VoyageEmbeddingProvider("k", "voyage-4-lite").name != \
           VoyageEmbeddingProvider("k", "voyage-4").name


# ── Provider selection ─────────────────────────────────────────────────────


def test_it_stays_offline_until_a_key_is_set(monkeypatch):
    """Same posture as email and billing: configured or inert, never half-on."""
    from app.core.config import get_settings
    from app.services.ai import embeddings

    embeddings.reset_embedding_provider()
    settings = get_settings()
    monkeypatch.setattr(settings, "voyage_api_key", None, raising=False)
    monkeypatch.setattr(settings, "embedding_provider", "auto", raising=False)
    try:
        assert isinstance(embeddings.get_embedding_provider(), HashingEmbeddingProvider)
    finally:
        embeddings.reset_embedding_provider()


def test_a_key_switches_it_on_without_any_other_setting(monkeypatch):
    """"auto" plus a key is the whole activation path — nobody should have to discover a
    second flag to make a configured provider actually run."""
    from app.core.config import get_settings
    from app.services.ai import embeddings

    embeddings.reset_embedding_provider()
    settings = get_settings()
    monkeypatch.setattr(settings, "voyage_api_key", "pa-test-key", raising=False)
    monkeypatch.setattr(settings, "embedding_provider", "auto", raising=False)
    monkeypatch.setattr(settings, "voyage_model", "voyage-4-lite", raising=False)
    try:
        provider = embeddings.get_embedding_provider()
        assert isinstance(provider, VoyageEmbeddingProvider)
        assert provider.name == "voyage:voyage-4-lite"
    finally:
        embeddings.reset_embedding_provider()


def test_hash_can_be_forced_even_with_a_key_present(monkeypatch):
    """An escape hatch that matters during an incident: turn the external dependency off
    without deleting the credential."""
    from app.core.config import get_settings
    from app.services.ai import embeddings

    embeddings.reset_embedding_provider()
    settings = get_settings()
    monkeypatch.setattr(settings, "voyage_api_key", "pa-test-key", raising=False)
    monkeypatch.setattr(settings, "embedding_provider", "hash", raising=False)
    try:
        assert isinstance(embeddings.get_embedding_provider(), HashingEmbeddingProvider)
    finally:
        embeddings.reset_embedding_provider()


def test_asking_for_voyage_without_a_key_refuses_instead_of_falling_back(monkeypatch):
    """Falling back would write hash vectors into a base the operator believes is on a real
    model — and the two are silently incomparable. Refusing is the kinder failure."""
    from app.core.config import get_settings
    from app.services.ai import embeddings

    embeddings.reset_embedding_provider()
    settings = get_settings()
    monkeypatch.setattr(settings, "voyage_api_key", None, raising=False)
    monkeypatch.setattr(settings, "embedding_provider", "voyage", raising=False)
    try:
        with pytest.raises(EmbeddingError):
            embeddings.get_embedding_provider()
    finally:
        embeddings.reset_embedding_provider()


async def test_embed_many_bounds_its_concurrency():
    """The backfill can face thousands of rows against a rate-limited API. Unbounded
    fan-out there is how a migration turns into a 429 storm."""
    peak = 0
    live = 0

    class Counting(FakeProvider):
        async def embed(self, text, *, purpose):
            nonlocal peak, live
            live += 1
            peak = max(peak, live)
            try:
                import asyncio
                await asyncio.sleep(0)
                return await super().embed(text, purpose=purpose)
            finally:
                live -= 1

    await embed_many(Counting(), [f"t{i}" for i in range(20)],
                     purpose="document", concurrency=3)
    assert peak <= 3


def _install(monkeypatch, handler) -> None:
    """Route the provider's httpx client at a mock transport."""
    transport = httpx.MockTransport(handler)
    real = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs.setdefault("transport", transport)
        return real(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)
