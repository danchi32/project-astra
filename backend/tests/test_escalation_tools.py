"""The escalation path as a conversation actually reaches it.

Until now the service existed and nothing called it. These tests cover the wiring: whether
the tools are offered at all, what happens when they are called out of order, and the
asynchronous case where a fix fails minutes after the user stopped watching.

The guard that matters most is negative — the tools must be invisible to any organization
that cannot file a ticket. A model that cannot see a tool cannot promise a ticket nobody
can raise, and "shall I raise a ticket?" followed by "sorry, I can't" is worse than never
having asked.
"""
import json
import uuid

import pytest

from app.core import crypto
from app.core.config import get_settings
from app.models import (
    Asset,
    Conversation,
    Device,
    HelpdeskSettings,
    Message,
    MessageRole,
    SupportEscalation,
    User,
    UserRole,
)
from app.models.support_escalation import EscalationState
from app.services.ai import escalation_tools
from app.services.support import requester


@pytest.fixture(autouse=True)
def _secrets_key(monkeypatch):
    monkeypatch.setattr(get_settings(), "secrets_key", crypto.generate_key(), raising=False)


async def _configure_helpdesk(session, org_id, **kw):
    session.add(HelpdeskSettings(
        org_id=org_id, enabled=kw.pop("enabled", True), domain="acme",
        api_key_encrypted=crypto.encrypt("fs-key"), **kw,
    ))
    await session.flush()


def _device(org_id, hostname, logged_in_user):
    """A Device with the columns the schema actually requires. Built directly rather than
    through enrolment because these tests are about who a ticket belongs to, not about
    enrolment."""
    return Device(
        org_id=org_id, hostname=hostname, machine_id=str(uuid.uuid4()),
        os_version="Windows 11", agent_version="0.7.4",
        token_hash=uuid.uuid4().hex, logged_in_user=logged_in_user,
    )


async def _device_with_user(session, org_id, email="priya@acme.com"):
    user = User(org_id=org_id, email=email, full_name="Priya", role=UserRole.USER)
    device = _device(org_id, "PC-1", "ACME\\priya")
    session.add_all([user, device])
    await session.flush()
    return device, user


# ── Whether the tools are offered at all ───────────────────────────────────


async def test_the_tools_are_hidden_when_no_helpdesk_is_connected(session_factory, admin_user):
    async with session_factory() as session:
        device, _ = await _device_with_user(session, admin_user.org_id)
        convo = Conversation(org_id=admin_user.org_id, device_id=device.id, title="c")
        session.add(convo)
        await session.flush()
        tools = await escalation_tools.available_for(
            session, org_id=admin_user.org_id, conversation_id=convo.id, device_id=device.id
        )
    assert tools == []


async def test_the_tools_are_hidden_when_nobody_can_be_named(session_factory, admin_user):
    """A ticket filed against the wrong person is worse than no ticket — their SLA clock
    runs for someone who never asked, and the person with the problem never hears back."""
    async with session_factory() as session:
        await _configure_helpdesk(session, admin_user.org_id)
        device = _device(admin_user.org_id, "PC-9", "ACME\\nobody")
        session.add(device)
        await session.flush()
        convo = Conversation(org_id=admin_user.org_id, device_id=device.id, title="c")
        session.add(convo)
        await session.flush()
        tools = await escalation_tools.available_for(
            session, org_id=admin_user.org_id, conversation_id=convo.id, device_id=device.id
        )
    assert tools == []


async def test_the_tools_appear_once_both_are_in_place(session_factory, admin_user):
    async with session_factory() as session:
        await _configure_helpdesk(session, admin_user.org_id)
        device, _ = await _device_with_user(session, admin_user.org_id)
        convo = Conversation(org_id=admin_user.org_id, device_id=device.id, title="c")
        session.add(convo)
        await session.flush()
        tools = await escalation_tools.available_for(
            session, org_id=admin_user.org_id, conversation_id=convo.id, device_id=device.id
        )
    assert {t["name"] for t in tools} == {escalation_tools.OFFER, escalation_tools.RAISE}


# ── Calling them ───────────────────────────────────────────────────────────


async def test_offering_asks_and_raising_files(session_factory, admin_user, monkeypatch):
    """The whole flow the user sees: a question, their answer, a ticket number."""
    import httpx

    def handler(request):
        return httpx.Response(201, json={"ticket": {"id": 7788}})

    transport = httpx.MockTransport(handler)
    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient",
                        lambda *a, **k: real(*a, **{**k, "transport": transport}))

    async with session_factory() as session:
        await _configure_helpdesk(session, admin_user.org_id)
        device, _ = await _device_with_user(session, admin_user.org_id)
        convo = Conversation(org_id=admin_user.org_id, device_id=device.id, title="c")
        session.add(convo)
        await session.flush()
        await session.commit()
        convo_id, device_id = convo.id, device.id

    async with session_factory() as session:
        offered = json.loads(await escalation_tools.dispatch(
            session=session, org_id=admin_user.org_id, name=escalation_tools.OFFER,
            tool_input={"problem": "outlook khul nahi raha",
                        "action_tried": "restart_outlook"},
            conversation_id=convo_id, device_id=device_id,
        ))
        assert offered["asked"] is True
        assert "?" in offered["say_to_user"]

        session.add(Message(conversation_id=convo_id, role=MessageRole.USER, content="haan"))
        await session.commit()

    async with session_factory() as session:
        raised = json.loads(await escalation_tools.dispatch(
            session=session, org_id=admin_user.org_id, name=escalation_tools.RAISE,
            tool_input={}, conversation_id=convo_id, device_id=device_id,
        ))

    assert raised["raised"] is True
    assert raised["ticket"] == "7788"
    assert "7788" in raised["say_to_user"]


async def test_raising_before_asking_tells_the_model_to_ask(session_factory, admin_user):
    """The model getting ahead of the user is reported back to it, not raised — so it can
    ask properly instead of the whole turn failing."""
    async with session_factory() as session:
        await _configure_helpdesk(session, admin_user.org_id)
        device, _ = await _device_with_user(session, admin_user.org_id)
        convo = Conversation(org_id=admin_user.org_id, device_id=device.id, title="c")
        session.add(convo)
        await session.flush()
        result = json.loads(await escalation_tools.dispatch(
            session=session, org_id=admin_user.org_id, name=escalation_tools.RAISE,
            tool_input={}, conversation_id=convo.id, device_id=device.id,
        ))
    assert result["raised"] is False
    assert "?" in result["say_to_user"]


async def test_an_offer_with_no_problem_text_is_rejected(session_factory, admin_user):
    """The user's words are the one part of the dossier that cannot be reconstructed
    later. An escalation without them is a ticket saying nothing."""
    async with session_factory() as session:
        await _configure_helpdesk(session, admin_user.org_id)
        device, _ = await _device_with_user(session, admin_user.org_id)
        convo = Conversation(org_id=admin_user.org_id, device_id=device.id, title="c")
        session.add(convo)
        await session.flush()
        result = json.loads(await escalation_tools.dispatch(
            session=session, org_id=admin_user.org_id, name=escalation_tools.OFFER,
            tool_input={"problem": "   "}, conversation_id=convo.id, device_id=device.id,
        ))
    assert "error" in result


async def test_unrelated_tool_names_are_left_alone(session_factory, admin_user):
    """dispatch() sits in front of every other tool. Returning anything for a name it does
    not own would swallow the rest of the toolset."""
    async with session_factory() as session:
        assert await escalation_tools.dispatch(
            session=session, org_id=admin_user.org_id, name="list_devices",
            tool_input={}, conversation_id=None, device_id=None,
        ) is None


# ── Who the ticket belongs to ──────────────────────────────────────────────


async def test_a_portal_chat_uses_the_signed_in_user(session_factory, admin_user):
    async with session_factory() as session:
        convo = Conversation(org_id=admin_user.org_id, user_id=admin_user.id, title="c")
        session.add(convo)
        await session.flush()
        who = await requester.resolve(session, org_id=admin_user.org_id,
                                      conversation_id=convo.id, device_id=None)
    assert who is not None and who.email == admin_user.email
    assert who.how == "conversation user"


async def test_an_assigned_asset_beats_whoever_is_signed_in(session_factory, admin_user):
    """An assignment is a deliberate act by an administrator: this laptop belongs to this
    person. Better evidence than whoever happens to be logged in right now."""
    async with session_factory() as session:
        device, _ = await _device_with_user(session, admin_user.org_id, "priya@acme.com")
        owner = User(org_id=admin_user.org_id, email="owner@acme.com",
                     full_name="Owner", role=UserRole.USER)
        session.add(owner)
        await session.flush()
        session.add(Asset(org_id=admin_user.org_id, name="Laptop", device_id=device.id,
                          assigned_to_user_id=owner.id))
        await session.flush()
        who = await requester.resolve(session, org_id=admin_user.org_id,
                                      conversation_id=None, device_id=device.id)
    assert who is not None and who.email == "owner@acme.com"
    assert who.how == "asset assignment"


async def test_the_windows_username_is_matched_to_a_real_account(session_factory, admin_user):
    """An inference, but a narrow one: the local part of an address we already hold, in
    this organization. It finds an account that exists rather than inventing one."""
    async with session_factory() as session:
        device, _ = await _device_with_user(session, admin_user.org_id, "priya@acme.com")
        who = await requester.resolve(session, org_id=admin_user.org_id,
                                      conversation_id=None, device_id=device.id)
    assert who is not None and who.email == "priya@acme.com"


async def test_an_unknown_windows_user_is_not_turned_into_an_address(session_factory,
                                                                     admin_user):
    """Never manufacture priya@<org domain>. A guessed address either bounces or creates a
    plausible-looking contact in the customer's helpdesk that nobody owns."""
    async with session_factory() as session:
        device = _device(admin_user.org_id, "PC-2", "ACME\\ghost")
        session.add(device)
        await session.flush()
        who = await requester.resolve(session, org_id=admin_user.org_id,
                                      conversation_id=None, device_id=device.id)
    assert who is None


async def test_no_device_and_no_conversation_resolves_to_nobody(session_factory, admin_user):
    async with session_factory() as session:
        assert await requester.resolve(session, org_id=admin_user.org_id,
                                       conversation_id=None, device_id=None) is None


async def test_a_device_nobody_is_signed_in_to_resolves_to_nobody(session_factory,
                                                                  admin_user):
    """A shared or unattended machine. There is no one to attribute the ticket to, and
    inventing someone is exactly what must not happen."""
    async with session_factory() as session:
        device = _device(admin_user.org_id, "KIOSK-1", None)
        session.add(device)
        await session.flush()
        assert await requester.resolve(session, org_id=admin_user.org_id,
                                       conversation_id=None, device_id=device.id) is None


async def test_an_assignment_to_another_orgs_user_is_ignored(session_factory, admin_user,
                                                             other_org):
    """Tenancy again, on the path that looks most trustworthy. An assignment row pointing
    across organizations must not become this org's requester."""
    async with session_factory() as session:
        stranger = User(org_id=other_org.id, email="stranger@other.com",
                        full_name="Stranger", role=UserRole.USER)
        device = _device(admin_user.org_id, "PC-8", None)
        session.add_all([stranger, device])
        await session.flush()
        session.add(Asset(org_id=admin_user.org_id, name="Laptop", device_id=device.id,
                          assigned_to_user_id=stranger.id))
        await session.flush()
        assert await requester.resolve(session, org_id=admin_user.org_id,
                                       conversation_id=None, device_id=device.id) is None


async def test_a_domain_only_logged_in_user_resolves_to_nobody(session_factory, admin_user):
    """The agent reports whatever Windows gives it. "ACME\\" with nothing after it would
    otherwise match the first account in the org whose email starts with "@"."""
    async with session_factory() as session:
        device = _device(admin_user.org_id, "PC-7", "ACME\\")
        session.add(device)
        await session.flush()
        assert await requester.resolve(session, org_id=admin_user.org_id,
                                       conversation_id=None, device_id=device.id) is None


async def test_escalation_outside_a_conversation_is_refused(session_factory, admin_user):
    """Both tools are anchored to a conversation: the offer lives in one, and consent is
    "a person spoke in this conversation after it". Without one there is nothing to
    anchor to."""
    async with session_factory() as session:
        result = json.loads(await escalation_tools.dispatch(
            session=session, org_id=admin_user.org_id, name=escalation_tools.OFFER,
            tool_input={"problem": "x"}, conversation_id=None, device_id=None,
        ))
    assert "error" in result


async def test_a_matching_name_in_another_org_is_not_used(session_factory, admin_user,
                                                          other_org):
    """Tenancy. "priya" existing somewhere else must never become this org's requester."""
    async with session_factory() as session:
        session.add(User(org_id=other_org.id, email="priya@other.com",
                         full_name="Priya", role=UserRole.USER))
        device = _device(admin_user.org_id, "PC-3", "OTHER\\priya")
        session.add(device)
        await session.flush()
        who = await requester.resolve(session, org_id=admin_user.org_id,
                                      conversation_id=None, device_id=device.id)
    assert who is None


# ── The asynchronous failure ───────────────────────────────────────────────


async def test_a_failed_fix_offers_a_ticket_in_the_conversation(client, admin_headers,
                                                                session_factory):
    """The common case, and the one a chat turn cannot serve: the fix fails minutes after
    the user stopped watching, so the offer is posted rather than waiting for a turn that
    may never come."""
    tok = await client.post("/api/v1/devices/enrollment-tokens",
                            json={"name": "esc"}, headers=admin_headers)
    enrolled = (await client.post("/api/v1/agent/enroll", json={
        "enrollment_token": tok.json()["token"], "hostname": "ESC-PC",
        "machine_id": "esc-pc", "os_version": "Windows 11", "agent_version": "0.7.4",
    })).json()
    device_headers = {"Authorization": f"Bearer {enrolled['device_token']}"}

    from sqlalchemy import select

    async with session_factory() as session:
        device = (await session.execute(
            select(Device).where(Device.machine_id == "esc-pc")
        )).scalars().one()
        await _configure_helpdesk(session, device.org_id)
        device.logged_in_user = "ACME\\priya"
        session.add(User(org_id=device.org_id, email="priya@acme.com",
                         full_name="Priya", role=UserRole.USER))
        await session.commit()
        org_id = device.org_id

    await client.post("/api/v1/agent/chat",
                      json={"content": "outlook is not responding"}, headers=device_headers)
    claimed = (await client.get("/api/v1/agent/tasks", headers=device_headers)).json()
    if not claimed:
        pytest.skip("the stub assistant proposed no remediation for this phrasing")

    await client.post(f"/api/v1/agent/tasks/{claimed[0]['id']}/result",
                      json={"success": False, "output": "Outlook did not restart"},
                      headers=device_headers)

    async with session_factory() as session:
        escalations = list((await session.execute(
            select(SupportEscalation).where(SupportEscalation.org_id == org_id)
        )).scalars())
        messages = list((await session.execute(select(Message.content))).scalars())

    assert escalations, "a failed fix should have produced an offer"
    assert escalations[0].state is EscalationState.OFFERED
    assert any("ticket" in m.lower() for m in messages), \
        "the offer has to reach the user, not just the database"


async def test_a_failed_fix_without_a_helpdesk_keeps_the_old_wording(
    client, admin_headers, session_factory
):
    """Unconfigured orgs must not be promised anything. They get what they got before."""
    tok = await client.post("/api/v1/devices/enrollment-tokens",
                            json={"name": "esc2"}, headers=admin_headers)
    enrolled = (await client.post("/api/v1/agent/enroll", json={
        "enrollment_token": tok.json()["token"], "hostname": "ESC2-PC",
        "machine_id": "esc2-pc", "os_version": "Windows 11", "agent_version": "0.7.4",
    })).json()
    device_headers = {"Authorization": f"Bearer {enrolled['device_token']}"}

    await client.post("/api/v1/agent/chat",
                      json={"content": "outlook is not responding"}, headers=device_headers)
    claimed = (await client.get("/api/v1/agent/tasks", headers=device_headers)).json()
    if not claimed:
        pytest.skip("the stub assistant proposed no remediation for this phrasing")

    resp = await client.post(f"/api/v1/agent/tasks/{claimed[0]['id']}/result",
                             json={"success": False, "output": "failed"},
                             headers=device_headers)
    assert resp.status_code == 204

    from sqlalchemy import select

    async with session_factory() as session:
        messages = list((await session.execute(select(Message.content))).scalars())
        escalations = list((await session.execute(select(SupportEscalation))).scalars())

    assert not escalations
    assert any("flagged it for your IT team" in m for m in messages)
