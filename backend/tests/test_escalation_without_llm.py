"""Answering "shall I raise a ticket?" when there is no LLM in the conversation.

The escalation service was reachable from exactly one place: the model's tool. The real
model runs only for ai_pro organizations, and none of them are — so in production ASTRA
asked the question after a failed fix, the user said yes, and nothing happened. The offer
stayed open forever and the user waited for a ticket that was never filed.

These pin the rules-driven path: the question means the same thing whoever is doing the
talking, and a reply that is not an answer is still not consent.
"""
import uuid

import httpx
import pytest

from app.core import crypto
from app.core.config import get_settings
from app.models import (
    Conversation,
    Device,
    HelpdeskSettings,
    Message,
    MessageRole,
    RemediationTask,
    SupportEscalation,
)
from app.models.remediation import RemediationSource, RemediationStatus
from app.models.support_escalation import EscalationState
from app.services.conversations import ConversationService
from app.services.support.connector import MockConnector
from app.services.support.dossier import Attempt, Dossier
from app.services.support.escalation import EscalationService


@pytest.fixture(autouse=True)
def _secrets_key(monkeypatch):
    monkeypatch.setattr(get_settings(), "secrets_key", crypto.generate_key(), raising=False)


@pytest.fixture
def _freshservice(monkeypatch):
    """Answer the ticket POST without leaving the process."""
    def handler(request):
        return httpx.Response(201, json={"ticket": {"id": 4242}})

    transport = httpx.MockTransport(handler)
    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient",
                        lambda *a, **k: real(*a, **{**k, "transport": transport}))


def _device(org_id) -> Device:
    return Device(
        org_id=org_id, hostname="PC-1", machine_id=str(uuid.uuid4()),
        os_version="Windows 11", agent_version="0.7.4", token_hash=uuid.uuid4().hex,
    )


async def _configure_helpdesk(session, org_id):
    session.add(HelpdeskSettings(
        org_id=org_id, enabled=True, domain="acme",
        api_key_encrypted=crypto.encrypt("fs-key"),
    ))
    await session.flush()


async def _conversation_with_offer(session, actor) -> uuid.UUID:
    """A conversation where ASTRA has already offered — the state a failed fix leaves."""
    convo = Conversation(org_id=actor.org_id, user_id=actor.id, title="chat")
    session.add(convo)
    await session.flush()
    await EscalationService(session, connector=MockConnector()).offer(
        org_id=actor.org_id, conversation_id=convo.id, device_id=None, user_id=actor.id,
        dossier=Dossier(problem="outlook keeps crashing", hostname="PC-1",
                        attempts=[Attempt(label="Restart Outlook", succeeded=False)]),
        action_id="restart_outlook",
    )
    await session.commit()
    return convo.id


async def _state(session_factory, convo_id) -> SupportEscalation:
    from sqlalchemy import select
    async with session_factory() as s:
        return (await s.execute(
            select(SupportEscalation).where(SupportEscalation.conversation_id == convo_id)
        )).scalars().first()


async def test_a_yes_raises_the_ticket_with_no_llm(
    session_factory, admin_user, _freshservice
):
    """The bug this exists for: the org is not ai_pro, so no model is in the loop at all."""
    async with session_factory() as session:
        await _configure_helpdesk(session, admin_user.org_id)
        await session.commit()
        convo_id = await _conversation_with_offer(session, admin_user)

    async with session_factory() as session:
        _, reply = await ConversationService(session).send_message(
            actor=admin_user, conversation_id=convo_id, content="haan kar do",
        )

    assert "4242" in reply.content
    row = await _state(session_factory, convo_id)
    assert row.state is EscalationState.RAISED
    assert row.external_ticket_id == "4242"


async def test_a_no_closes_the_offer_for_good(session_factory, admin_user, _freshservice):
    """Declining has to stick. An offer left open is one a later stray "ok" can file."""
    async with session_factory() as session:
        await _configure_helpdesk(session, admin_user.org_id)
        await session.commit()
        convo_id = await _conversation_with_offer(session, admin_user)

    async with session_factory() as session:
        _, reply = await ConversationService(session).send_message(
            actor=admin_user, conversation_id=convo_id, content="nahi, rehne do",
        )
    assert "won't raise" in reply.content.lower()
    assert (await _state(session_factory, convo_id)).state is EscalationState.DECLINED

    async with session_factory() as session:
        await ConversationService(session).send_message(
            actor=admin_user, conversation_id=convo_id, content="haan kar do",
        )
    row = await _state(session_factory, convo_id)
    assert row.state is EscalationState.DECLINED
    assert row.external_ticket_id is None


async def test_a_follow_up_is_not_an_answer(session_factory, admin_user, _freshservice):
    """"ok so outlook is still crashing" starts with "ok" and is not consent to anything.

    The offer sits open for the rest of the conversation, so the next message is far more
    likely to be a follow-up than an answer.
    """
    async with session_factory() as session:
        await _configure_helpdesk(session, admin_user.org_id)
        await session.commit()
        convo_id = await _conversation_with_offer(session, admin_user)

    async with session_factory() as session:
        _, reply = await ConversationService(session).send_message(
            actor=admin_user, conversation_id=convo_id, content="ok so outlook is still crashing",
        )

    row = await _state(session_factory, convo_id)
    assert row.state is EscalationState.OFFERED   # still open, still unanswered
    assert row.external_ticket_id is None
    assert "4242" not in reply.content


async def test_a_yes_with_no_offer_open_is_just_a_message(
    session_factory, admin_user, _freshservice
):
    """Nothing was asked, so "yes" agrees to nothing — and must not file anything.

    Also pins the guard on the dead-end branch: an unhandled pleasantry is not a complaint,
    and ASTRA must not offer to open a ticket about one.
    """
    async with session_factory() as session:
        await _configure_helpdesk(session, admin_user.org_id)
        convo = Conversation(org_id=admin_user.org_id, user_id=admin_user.id, title="chat")
        session.add(convo)
        await session.flush()
        await session.commit()
        convo_id = convo.id

    async with session_factory() as session:
        await ConversationService(session).send_message(
            actor=admin_user, conversation_id=convo_id, content="yes please",
        )

    assert await _state(session_factory, convo_id) is None


# ── Stepping to the next tier when a fix did not help ───────────────────────


async def _conversation_with_a_failed_attempt(session, actor, device):
    """A chat where ASTRA restarted something and the user is about to say it didn't help."""
    convo = Conversation(org_id=actor.org_id, user_id=actor.id, title="chat")
    session.add(convo)
    await session.flush()
    session.add(Message(conversation_id=convo.id, role=MessageRole.USER,
                        content="outlook keeps crashing"))
    session.add(RemediationTask(
        org_id=actor.org_id, device_id=device.id, action_id="restart_outlook",
        tier="automatic", status=RemediationStatus.SUCCEEDED, reason="chat",
        source=RemediationSource.ASSISTANT, conversation_id=convo.id,
    ))
    await session.flush()
    await session.commit()
    return convo.id


async def test_still_broken_after_a_fix_offers_a_ticket(
    session_factory, admin_user, _freshservice
):
    """Not ai_pro, so there is no model to escalate to — the ticket is the next tier.

    The built-in rules would otherwise match "still crashing" against the same keyword that
    produced the restart and restart Outlook again.
    """
    async with session_factory() as session:
        await _configure_helpdesk(session, admin_user.org_id)
        device = _device(admin_user.org_id)
        session.add(device)
        await session.flush()
        convo_id = await _conversation_with_a_failed_attempt(session, admin_user, device)

    async with session_factory() as session:
        _, reply = await ConversationService(session).send_message(
            actor=admin_user, conversation_id=convo_id,
            content="outlook is still crashing, koi fark nahi pada",
        )

    assert "ticket" in reply.content.lower()
    row = await _state(session_factory, convo_id)
    assert row is not None and row.state is EscalationState.OFFERED
    # And the dossier carries what was already tried, so a technician does not repeat it.
    assert "Restart Outlook" in (row.dossier or "")


async def test_still_broken_goes_to_the_model_when_ai_pro(
    session_factory, admin_user, monkeypatch, _freshservice
):
    """With a model available, it investigates — and it owns the ticket question, so the
    rules path must not ask as well. Two owners in one turn is two offers."""
    from app.services.ai.provider import StubProvider

    async with session_factory() as session:
        await _configure_helpdesk(session, admin_user.org_id)
        device = _device(admin_user.org_id)
        session.add(device)
        await session.flush()
        convo_id = await _conversation_with_a_failed_attempt(session, admin_user, device)

    from app.models import Organization
    async with session_factory() as session:
        org = await session.get(Organization, admin_user.org_id)
        org.ai_pro = True
        await session.commit()

    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-test", raising=False)
    seen: list[str] = []

    class _Recorder(StubProvider):
        async def generate(self, **kwargs):
            seen.append("called")
            return await super().generate(**kwargs)

    monkeypatch.setattr("app.services.conversations.get_provider", lambda: _Recorder())

    async with session_factory() as session:
        await ConversationService(session).send_message(
            actor=admin_user, conversation_id=convo_id,
            content="outlook is still crashing, koi fark nahi pada",
        )

    # At least once — the engine is a tool-use loop, so one turn is several generate calls.
    assert seen, "the real provider should have answered this turn"
    assert await _state(session_factory, convo_id) is None, \
        "the rules path must not offer when the model owns the question"


async def test_still_broken_wording_does_not_skip_the_built_in_tier(
    session_factory, admin_user, _freshservice
):
    """Nothing has been tried yet, so "still not working" is just how they phrased it.

    The tier step is about a fix that failed, not about a form of words — otherwise the
    first message of a chat would jump straight past the fix ASTRA can apply for free.
    Outlook, because the built-in rules do own Outlook.
    """
    async with session_factory() as session:
        await _configure_helpdesk(session, admin_user.org_id)
        convo = Conversation(org_id=admin_user.org_id, user_id=admin_user.id, title="chat")
        session.add(convo)
        await session.flush()
        await session.commit()
        convo_id = convo.id

    async with session_factory() as session:
        await ConversationService(session).send_message(
            actor=admin_user, conversation_id=convo_id,
            content="outlook is still not working",
        )

    assert await _state(session_factory, convo_id) is None


async def test_an_unfixable_problem_is_offered_a_ticket_straight_away(
    session_factory, admin_user, _freshservice
):
    """No built-in rule covers a snapped-off key and there is no model to think about it.

    This is the reply the live test found in production: ASTRA answered a broken keyboard
    with "tell me what's going wrong and I'll take care of it".
    """
    async with session_factory() as session:
        await _configure_helpdesk(session, admin_user.org_id)
        device = _device(admin_user.org_id)
        session.add(device)
        convo = Conversation(org_id=admin_user.org_id, user_id=admin_user.id, title="chat")
        session.add(convo)
        await session.flush()
        await session.commit()
        convo_id = convo.id

    async with session_factory() as session:
        _, reply = await ConversationService(session).send_message(
            actor=admin_user, conversation_id=convo_id,
            content="the enter key on my keyboard is physically broken and won't press down",
        )

    assert "ticket" in reply.content.lower()
    row = await _state(session_factory, convo_id)
    assert row is not None and row.state is EscalationState.OFFERED


async def test_nothing_is_offered_without_a_helpdesk(session_factory, admin_user):
    """No connector means no promise. The old greeting is a poor answer; a ticket that
    cannot be filed is a worse one."""
    async with session_factory() as session:
        device = _device(admin_user.org_id)
        session.add(device)
        await session.flush()
        convo_id = await _conversation_with_a_failed_attempt(session, admin_user, device)

    async with session_factory() as session:
        _, reply = await ConversationService(session).send_message(
            actor=admin_user, conversation_id=convo_id,
            content="outlook is still crashing, koi fark nahi pada",
        )

    assert await _state(session_factory, convo_id) is None
    assert "ticket" not in reply.content.lower()
