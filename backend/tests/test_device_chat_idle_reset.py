"""A tray chat is a visit, not a mailbox.

Reported from the field: someone had their browser cache cleared, came back much later,
asked to change their time zone — and was answered about the cache again. The thread had
never ended, so every new question arrived with the old problem still attached, and both
the rules and the model read it as a continuation.

Past the idle window the next message therefore starts a new conversation, and reopening
the window shows an empty one. Enforced server-side rather than in the tray, so it applies
to every agent version already installed rather than only to whatever ships next.
"""
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models import Conversation, Message
from app.models.base import utcnow


async def _enroll(client, admin_headers, machine="idle-machine"):
    token = await client.post(
        "/api/v1/devices/enrollment-tokens", json={"name": "idle"}, headers=admin_headers
    )
    enrolled = await client.post("/api/v1/agent/enroll", json={
        "enrollment_token": token.json()["token"], "hostname": "IDLE-PC",
        "machine_id": machine, "os_version": "Windows 11", "agent_version": "0.8.3",
    })
    return {"Authorization": f"Bearer {enrolled.json()['device_token']}"}


async def _say(client, headers, text, conversation_id=None):
    body = {"content": text}
    if conversation_id is not None:
        body["conversation_id"] = str(conversation_id)
    resp = await client.post("/api/v1/agent/chat", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _age_conversation(session_factory, conversation_id, minutes):
    """Push every message in a conversation into the past."""
    async with session_factory() as session:
        rows = (await session.execute(
            select(Message).where(Message.conversation_id == uuid.UUID(str(conversation_id)))
        )).scalars().all()
        for row in rows:
            row.created_at = utcnow() - timedelta(minutes=minutes)
        convo = await session.get(Conversation, uuid.UUID(str(conversation_id)))
        convo.created_at = utcnow() - timedelta(minutes=minutes)
        await session.commit()


@pytest.fixture
def idle_minutes():
    return get_settings().device_chat_idle_minutes


async def test_a_reply_within_the_window_continues_the_same_chat(client, admin_headers):
    headers = await _enroll(client, admin_headers)
    first = await _say(client, headers, "my laptop is slow")
    second = await _say(client, headers, "still slow", conversation_id=first["conversation_id"])
    assert second["conversation_id"] == first["conversation_id"]


async def test_a_message_after_the_idle_window_starts_a_new_chat(
    client, admin_headers, session_factory, idle_minutes
):
    headers = await _enroll(client, admin_headers)
    first = await _say(client, headers, "clear my browser cache")
    await _age_conversation(session_factory, first["conversation_id"], idle_minutes + 1)

    # The tray still sends the id it was holding; the server is what decides it is stale.
    second = await _say(client, headers, "change my timezone to IST",
                        conversation_id=first["conversation_id"])
    assert second["conversation_id"] != first["conversation_id"]


async def test_the_new_chat_carries_none_of_the_old_conversation(
    client, admin_headers, session_factory, idle_minutes
):
    """The point of the reset. The old thread is what made the assistant answer the old
    question, so the fresh one must start with only what was just said."""
    headers = await _enroll(client, admin_headers)
    first = await _say(client, headers, "clear my browser cache")
    await _age_conversation(session_factory, first["conversation_id"], idle_minutes + 1)
    second = await _say(client, headers, "change my timezone to IST",
                        conversation_id=first["conversation_id"])

    async with session_factory() as session:
        messages = (await session.execute(
            select(Message)
            .where(Message.conversation_id == uuid.UUID(str(second["conversation_id"])))
            .order_by(Message.created_at)
        )).scalars().all()

    assert not any("cache" in m.content.lower() for m in messages), (
        [m.content for m in messages]
    )
    assert messages[0].content == "change my timezone to IST"


async def test_reopening_after_the_window_shows_an_empty_window(
    client, admin_headers, session_factory, idle_minutes
):
    """What the user actually sees. Restoring a transcript that the next message would not
    continue is worse than showing none — it looks like the assistant is still on the old
    problem."""
    headers = await _enroll(client, admin_headers)
    first = await _say(client, headers, "teams nahi khul raha")

    live = await client.get("/api/v1/agent/conversation", headers=headers)
    assert live.json()["messages"], "an active chat must still be restored"

    await _age_conversation(session_factory, first["conversation_id"], idle_minutes + 1)
    stale = await client.get("/api/v1/agent/conversation", headers=headers)
    assert stale.json()["messages"] == []
    assert stale.json()["conversation_id"] is None


async def test_the_reset_can_be_switched_off(
    client, admin_headers, session_factory, monkeypatch
):
    """Zero means never reset — an escape hatch if an organization wants the old behaviour,
    without needing a code change to get it back."""
    settings = get_settings()
    monkeypatch.setattr(settings, "device_chat_idle_minutes", 0)

    headers = await _enroll(client, admin_headers, machine="never-reset")
    first = await _say(client, headers, "my laptop is slow")
    await _age_conversation(session_factory, first["conversation_id"], 600)
    second = await _say(client, headers, "any update?", conversation_id=first["conversation_id"])
    assert second["conversation_id"] == first["conversation_id"]
