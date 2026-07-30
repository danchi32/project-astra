"""The chat tells the user when a fix actually starts, not only when it finishes.

"Approved and queued" and "running on your PC now" are different states, and the gap between
them is the agent's poll interval — which grows as polling is made less frequent to cut
traffic. Without this the chat goes silent for that whole window.
"""
from sqlalchemy import select

from app.core.security import hash_opaque_token
from app.models import Conversation, Device, Message, MessageRole, RemediationSource
from app.models.base import utcnow
from app.services.remediation.service import RemediationService


async def _device_and_conversation(session_factory, org, admin_user, machine="chat-1"):
    async with session_factory() as s:
        device = Device(
            org_id=org.id, hostname="CHAT-PC", machine_id=machine,
            os_version="Windows 11", agent_version="0.6.4",
            token_hash=hash_opaque_token(f"tok-{machine}"), last_seen_at=utcnow(),
        )
        s.add(device)
        await s.flush()
        convo = Conversation(org_id=org.id, device_id=device.id, user_id=admin_user.id,
                             title="Chat progress test")
        s.add(convo)
        await s.commit()
        return device.id, convo.id, f"tok-{machine}"


async def _messages(session_factory, conversation_id):
    async with session_factory() as s:
        rows = (await s.execute(
            select(Message.role, Message.content).where(Message.conversation_id == conversation_id)
        )).all()
        return [c for r, c in rows if r is MessageRole.ASSISTANT]


async def test_chat_is_told_when_the_fix_starts(client, session_factory, org, admin_user):
    device_id, convo_id, token = await _device_and_conversation(session_factory, org, admin_user)

    async with session_factory() as s:
        device = await s.get(Device, device_id)
        await RemediationService(s).create_task(
            org_id=org.id, device=device, action_id="clear_temp", params=None,
            reason="chat progress test", source=RemediationSource.USER,
            actor_user_id=admin_user.id, conversation_id=convo_id,
        )

    # Nothing yet — the task is only queued.
    assert not any("Working on it" in m for m in await _messages(session_factory, convo_id))

    # The tray claims it: that is the moment it starts running on the PC.
    await client.get("/api/v1/agent/tasks", headers={"Authorization": f"Bearer {token}"})

    msgs = await _messages(session_factory, convo_id)
    assert any("Working on it" in m for m in msgs), msgs
    # Names the actual fix rather than a generic "please wait".
    assert any("temp" in m.lower() for m in msgs), msgs


async def test_no_chat_message_for_a_portal_pushed_fix(client, session_factory, org, admin_user):
    """A fix pushed from the portal has no conversation — there is nobody in a chat to tell,
    and inventing a conversation would be worse than silence."""
    device_id, _convo_id, token = await _device_and_conversation(
        session_factory, org, admin_user, machine="chat-2")

    async with session_factory() as s:
        device = await s.get(Device, device_id)
        await RemediationService(s).create_task(
            org_id=org.id, device=device, action_id="clear_temp", params=None,
            reason="portal push", source=RemediationSource.USER,
            actor_user_id=admin_user.id,          # no conversation_id
        )

    r = await client.get("/api/v1/agent/tasks", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert len(r.json()) == 1                      # still dispatched normally


async def test_start_and_finish_messages_both_land(client, session_factory, org, admin_user):
    """The user should see the whole arc: started, then the outcome."""
    device_id, convo_id, token = await _device_and_conversation(
        session_factory, org, admin_user, machine="chat-3")

    async with session_factory() as s:
        device = await s.get(Device, device_id)
        task = await RemediationService(s).create_task(
            org_id=org.id, device=device, action_id="clear_temp", params=None,
            reason="arc test", source=RemediationSource.USER,
            actor_user_id=admin_user.id, conversation_id=convo_id,
        )
        task_id = task.id

    h = {"Authorization": f"Bearer {token}"}
    await client.get("/api/v1/agent/tasks", headers=h)
    await client.post(f"/api/v1/agent/tasks/{task_id}/result", headers=h,
                      json={"success": True, "output": "Freed 2.1 GB"})

    msgs = await _messages(session_factory, convo_id)
    assert any("Working on it" in m for m in msgs), msgs

    done = next(m for m in msgs if m.startswith("✅"))
    # Says what was actually done, naming the mechanism — not "your PC should be better now".
    assert "%TEMP%" in done, done
    # And carries the agent's own measurement, which used to be computed and discarded.
    assert "Freed 2.1 GB" in done, done


async def test_completion_message_survives_an_agent_that_reports_nothing(
    client, session_factory, org, admin_user
):
    """Not every action returns a measurement. The explanation must still stand on its own."""
    device_id, convo_id, token = await _device_and_conversation(
        session_factory, org, admin_user, machine="chat-4")

    async with session_factory() as s:
        device = await s.get(Device, device_id)
        task = await RemediationService(s).create_task(
            org_id=org.id, device=device, action_id="flush_dns", params=None,
            reason="no-output test", source=RemediationSource.USER,
            actor_user_id=admin_user.id, conversation_id=convo_id,
        )
        task_id = task.id

    h = {"Authorization": f"Bearer {token}"}
    await client.get("/api/v1/agent/tasks", headers=h)
    await client.post(f"/api/v1/agent/tasks/{task_id}/result", headers=h,
                      json={"success": True, "output": ""})

    done = next(m for m in await _messages(session_factory, convo_id) if m.startswith("✅"))
    assert "DNS resolver cache" in done, done
    # No artefacts from the absent output: no stray "None", and no line left with dangling
    # whitespace where the measurement would have gone. (Blank lines between paragraphs are
    # intentional, so compare line by line rather than collapsing newlines.)
    assert "None" not in done, done
    assert all(line == line.strip() for line in done.splitlines()), repr(done)
