"""Tests for the AI cost controls: the intent gate rejects off-topic queries with no
LLM call, and the semantic cache serves repeated questions without the engine."""
from app.services.ai.embeddings import HashingEmbeddingProvider, cosine_similarity
from app.services.ai.intent import is_off_topic


# ── Intent gate (unit) ─────────────────────────────────────────────────────


def test_it_queries_pass_the_gate():
    for q in [
        "my laptop is slow",
        "outlook won't open",
        "I can't connect to the wifi",
        "how do I reset my password",
        "the printer isn't working",
    ]:
        assert is_off_topic(q) is False, q


def test_clearly_off_topic_queries_are_blocked():
    for q in [
        "write me a poem about the ocean",
        "give me a recipe for pasta",
        "what is the capital of France",
        "tell me a joke",
        "translate hello into Spanish",
    ]:
        assert is_off_topic(q) is True, q


def test_ambiguous_queries_fail_open():
    # No IT keyword and no off-topic marker → allowed (better than blocking real help).
    assert is_off_topic("something is wrong here") is False


# ── Embeddings (unit) ──────────────────────────────────────────────────────


async def test_similar_text_has_high_similarity():
    embed = HashingEmbeddingProvider()
    a = await embed.embed("how do I reset my password")
    b = await embed.embed("how can I reset my password")
    c = await embed.embed("the printer is jammed")
    assert cosine_similarity(a, b) > cosine_similarity(a, c)
    assert cosine_similarity(a, a) > 0.99  # identical text


# ── End-to-end through the device chat ─────────────────────────────────────


async def _enroll(client, admin_headers):
    tok = await client.post(
        "/api/v1/devices/enrollment-tokens", json={"name": "cost"}, headers=admin_headers
    )
    enroll = await client.post(
        "/api/v1/agent/enroll",
        json={
            "enrollment_token": tok.json()["token"],
            "hostname": "COST-PC",
            "machine_id": "cost-pc",
            "os_version": "Windows 11",
            "agent_version": "0.1.0",
        },
    )
    return {"Authorization": f"Bearer {enroll.json()['device_token']}"}


async def test_off_topic_query_hits_intent_gate(client, admin_headers):
    device_headers = await _enroll(client, admin_headers)
    resp = await client.post(
        "/api/v1/agent/chat",
        json={"content": "write me a poem about my cat"},
        headers=device_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "intent_gate"  # no LLM call was made
    assert "IT assistant" in body["reply"]
    assert not body["tool_trail"]


async def test_repeated_general_question_is_served_from_cache(client, admin_headers):
    device_headers = await _enroll(client, admin_headers)
    q = "what are your support hours"  # general, device-independent, no tools

    first = await client.post(
        "/api/v1/agent/chat", json={"content": q}, headers=device_headers
    )
    assert first.status_code == 200
    assert first.json()["source"] == "engine"  # first time → engine ran

    second = await client.post(
        "/api/v1/agent/chat", json={"content": q}, headers=device_headers
    )
    assert second.status_code == 200
    assert second.json()["source"] == "cache"  # repeat → served for free
    assert second.json()["reply"] == first.json()["reply"]


async def test_device_specific_answers_are_not_cached(client, admin_headers):
    device_headers = await _enroll(client, admin_headers)
    # A diagnostic query triggers tools (device-specific) — must NOT be cached.
    q = "is my cpu health okay"
    first = await client.post(
        "/api/v1/agent/chat", json={"content": q}, headers=device_headers
    )
    assert first.json()["source"] == "engine"
    assert first.json()["tool_trail"]  # gathered device evidence
    second = await client.post(
        "/api/v1/agent/chat", json={"content": q}, headers=device_headers
    )
    # Still engine (not cached), because the answer depends on live device state.
    assert second.json()["source"] == "engine"


async def test_cache_is_org_scoped(client, admin_headers, other_org, session_factory):
    from app.core.security import hash_opaque_token
    from app.models import Device

    device_headers = await _enroll(client, admin_headers)
    q = "what is the vpn address"
    await client.post("/api/v1/agent/chat", json={"content": q}, headers=device_headers)

    # A device in another org must not get this org's cached answer.
    async with session_factory() as session:
        other_device = Device(
            org_id=other_org.id, hostname="OTHER-PC", machine_id="other-pc",
            os_version="Windows 11", agent_version="0.1.0",
            token_hash=hash_opaque_token("other-cost-token"),
        )
        session.add(other_device)
        await session.commit()

    other_headers = {"Authorization": "Bearer other-cost-token"}
    resp = await client.post("/api/v1/agent/chat", json={"content": q}, headers=other_headers)
    assert resp.json()["source"] == "engine"  # not served from the first org's cache
