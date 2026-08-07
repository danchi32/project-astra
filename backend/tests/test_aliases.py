"""Bridging the gap between what technicians write and what users type.

Two mechanisms, one problem. Aliases put the user's words into the article; stemming and
stopwords widen what counts as a shared word. Neither is semantic search, and the tests
that matter most are the ones pinning what they DON'T promise.
"""
import pytest

from app.services.ai.aliases import MAX_ALIASES, AliasGenerator, _parse, embedding_text
from app.services.ai.embeddings import (
    HashingEmbeddingProvider,
    cosine_similarity,
    normalise,
)
from app.services.ai.knowledge import KnowledgeBaseService
from app.services.ai.provider import LLMResponse


class FakeLLM:
    """Returns whatever reply the test wants, and records what it was asked."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    async def generate(self, *, system, messages, tools) -> LLMResponse:
        self.prompts.append(messages[0]["content"])
        return LLMResponse(text=self.reply)


class BrokenLLM:
    async def generate(self, *, system, messages, tools) -> LLMResponse:
        raise RuntimeError("model is down")


# ── The actual problem being solved ────────────────────────────────────────


async def test_a_users_words_find_a_technicians_article(session_factory, admin_user):
    """The whole point, end to end.

    "mera laptop bahut slow hai" and "High memory utilization troubleshooting" share not
    one word. Before aliases this article was unfindable by the person who needed it.
    """
    llm = FakeLLM('["mera laptop bahut slow hai", "system hang ho raha hai", "laptop is slow"]')

    async with session_factory() as session:
        svc = KnowledgeBaseService(session, aliases=AliasGenerator(provider=llm))
        await svc.create(
            org_id=admin_user.org_id,
            title="High memory utilization troubleshooting",
            content="Check committed bytes and per-process working set. Restart offenders.",
        )

    async with session_factory() as session:
        hits = await KnowledgeBaseService(session).search(
            org_id=admin_user.org_id, query="mera laptop bahut slow hai"
        )
    assert [a.title for a in hits] == ["High memory utilization troubleshooting"]


async def test_without_aliases_that_same_search_finds_nothing(session_factory, admin_user):
    """The control. Without this the test above proves nothing — it could be passing on
    some accidental token overlap rather than on the aliases."""
    async with session_factory() as session:
        svc = KnowledgeBaseService(session, aliases=AliasGenerator(provider=FakeLLM("[]")))
        await svc.create(
            org_id=admin_user.org_id,
            title="High memory utilization troubleshooting",
            content="Check committed bytes and per-process working set. Restart offenders.",
        )

    async with session_factory() as session:
        hits = await KnowledgeBaseService(session).search(
            org_id=admin_user.org_id, query="mera laptop bahut slow hai"
        )
    assert hits == []


async def test_aliases_are_matched_against_but_not_shown(session_factory, admin_user):
    """The article a technician wrote must read the way they wrote it. Eight paraphrases of
    "it's broken" stapled underneath would make it findable and worse."""
    llm = FakeLLM('["laptop slow", "system hang"]')
    async with session_factory() as session:
        article = await KnowledgeBaseService(
            session, aliases=AliasGenerator(provider=llm)
        ).create(org_id=admin_user.org_id, title="Memory", content="Check working set.")

    assert article.content == "Check working set."
    assert "laptop slow" not in article.content
    assert article.symptom_samples == ["laptop slow", "system hang"]


def test_embedding_text_includes_aliases_but_content_does_not():
    text = embedding_text("Memory", "Check working set.", ["laptop slow"])
    assert "laptop slow" in text and "Check working set." in text


# ── Failing safely ─────────────────────────────────────────────────────────


async def test_an_article_still_saves_when_the_model_is_down(session_factory, admin_user):
    """Aliases are an enhancement; the technician's writing is the work. Losing the article
    because the model was busy would be a far worse trade than losing the aliases."""
    async with session_factory() as session:
        article = await KnowledgeBaseService(
            session, aliases=AliasGenerator(provider=BrokenLLM())
        ).create(org_id=admin_user.org_id, title="VPN", content="Open GlobalConnect.")
    assert article.title == "VPN"
    assert article.symptom_samples is None


async def test_it_is_inert_without_a_key(session_factory, admin_user, monkeypatch):
    """Same posture as email, billing and embeddings: configured or off, never half-on."""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "anthropic_api_key", None, raising=False)
    async with session_factory() as session:
        article = await KnowledgeBaseService(session).create(
            org_id=admin_user.org_id, title="VPN", content="Open GlobalConnect."
        )
    assert article.symptom_samples is None


@pytest.mark.parametrize("reply", [
    "",
    "I'm sorry, I can't help with that.",
    "{}",
    '["ok"',
    "null",
])
def test_junk_replies_yield_no_aliases_rather_than_junk_aliases(reply):
    assert _parse(reply) == []


@pytest.mark.parametrize("reply", [
    '```json\n["laptop slow", "system hang"]\n```',
    'Here you go:\n["laptop slow", "system hang"]',
    '["laptop slow", "system hang"]',
])
def test_it_tolerates_the_usual_model_wrappers(reply):
    """Models wrap JSON in fences or preface it with a sentence. Losing every alias to a
    stray backtick would be a silly way to lose the feature."""
    assert _parse(reply) == ["laptop slow", "system hang"]


def test_aliases_are_capped_and_deduped():
    reply = '["a phrase", "A PHRASE", ' + ", ".join(f'"p{i}"' for i in range(20)) + "]"
    out = _parse(reply)
    assert len(out) <= MAX_ALIASES
    assert len({a.lower() for a in out}) == len(out)


def test_non_string_items_are_dropped():
    assert _parse('["laptop slow", 42, null, {"x": 1}, "system hang"]') == [
        "laptop slow", "system hang",
    ]


async def test_the_prompt_asks_for_hinglish():
    """End users here write Hinglish — the codebase already assumes it elsewhere. An
    English-only alias set would miss the phrasings that actually get typed."""
    llm = FakeLLM("[]")
    await AliasGenerator(provider=llm).for_article(title="T", content="C")
    assert "hinglish" in llm.prompts[0].lower()


# ── Stemming and stopwords ─────────────────────────────────────────────────


@pytest.mark.parametrize("a,b", [
    ("printing", "printer"),
    ("prints", "print"),
    ("freezing", "freeze"),
    ("crashes", "crash"),
    ("restarted", "restart"),
])
def test_inflections_collapse_together(a, b):
    """A technician writes "printer", a user writes "printing". Before stemming those were
    two unrelated tokens."""
    assert normalise(a) == normalise(b), f"{a} vs {b}"


def test_stopwords_stop_inflating_unrelated_matches():
    """Two unrelated complaints share "my", "is", "not", "hai" and nothing else. Without
    stopword removal that shared scaffolding is most of a short query's signal."""
    assert normalise("my printer is not working hai") == normalise("printer work")
    # And the scaffolding on its own carries nothing at all.
    assert normalise("my is not the hai nahi raha") == []


async def test_a_query_still_beats_an_unrelated_article():
    """Guard against over-stemming: if everything collapses to the same stem, similarity
    becomes meaningless in the other direction."""
    p = HashingEmbeddingProvider()
    q = await p.embed("printer not printing", purpose="query")
    near = await p.embed("printers keep failing to print", purpose="document")
    far = await p.embed("how to request annual leave", purpose="document")
    assert cosine_similarity(q, near) > cosine_similarity(q, far)


def test_short_words_and_error_codes_survive_intact():
    """Over-stemming short tokens destroys them, and an error code is the single most
    searchable string in a support conversation — it must come through unchanged."""
    assert normalise("dns 0x80070005 vpn") == ["dns", "0x80070005", "vpn"]


# ── The version bump, which is the dangerous part ──────────────────────────


def test_changing_tokenization_changed_the_vector_space_name():
    """Stemming produces different vectors for the same text. If the name had not moved,
    search would compare v1 and v2 vectors — and score every pre-existing article at zero
    with no error anywhere. This is the same trap the model tag was built for."""
    assert HashingEmbeddingProvider().name == "hash-v2-256"
    assert HashingEmbeddingProvider().name != "hash-256"


async def test_old_articles_are_skipped_until_re_embedded(session_factory, admin_user, caplog):
    """End to end for the bump: a v1 row is not scored against a v2 query, and the skip is
    reported so "no results" is attributable."""
    from sqlalchemy import select

    from app.models import KnowledgeArticle

    async with session_factory() as session:
        await KnowledgeBaseService(session).create(
            org_id=admin_user.org_id, title="Connecting to the VPN",
            content="Open GlobalConnect and authenticate with MFA.",
        )

    async with session_factory() as session:
        article = (await session.execute(select(KnowledgeArticle))).scalars().first()
        article.embedding_model = "hash-256"  # as written before the bump
        await session.commit()

    async with session_factory() as session:
        with caplog.at_level("WARNING"):
            hits = await KnowledgeBaseService(session).search(
                org_id=admin_user.org_id, query="connecting to the VPN"
            )
    assert hits == []
    assert "reembed" in caplog.text
