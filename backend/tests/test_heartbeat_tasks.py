"""System-context tasks delivered on the heartbeat (removes the Service's separate poll).

The rollout hazard these guard: claiming marks a task dispatched. If the heartbeat claimed
tasks for an agent that doesn't read them, the work would vanish from the separate poller that
agent still relies on — self-healing would stop for every device on an older build, silently.
So the behaviour must be strictly opt-in.
"""
from app.core.security import hash_opaque_token
from app.models import Device, RemediationSource
from app.models.base import utcnow
from app.services.remediation.service import RemediationService


async def _device(session_factory, org, machine="hb-1"):
    async with session_factory() as s:
        d = Device(
            org_id=org.id, hostname="HB-PC", machine_id=machine,
            os_version="Windows 11", agent_version="0.6.4",
            token_hash=hash_opaque_token(f"tok-{machine}"), last_seen_at=utcnow(),
        )
        s.add(d)
        await s.commit()
        return d.id, f"tok-{machine}"


async def _approved_system_task(session_factory, org, device_id, admin_user):
    """Queue an approved system-context task (clear_system_temp runs in the elevated service)."""
    async with session_factory() as s:
        device = await s.get(Device, device_id)
        svc = RemediationService(s)
        task = await svc.create_task(
            org_id=org.id, device=device, action_id="clear_system_temp", params=None,
            reason="test", source=RemediationSource.USER, actor_user_id=admin_user.id,
        )
        return task.id


def _hb(token, **body):
    return {"headers": {"Authorization": f"Bearer {token}"},
            "json": {"agent_version": "0.6.4", **body}}


async def test_old_agent_heartbeat_never_claims_tasks(client, session_factory, org, admin_user):
    """An agent that doesn't ask must get nothing — and the task must still be waiting for
    its separate poll. This is the regression that would break self-healing mid-rollout."""
    device_id, token = await _device(session_factory, org)
    await _approved_system_task(session_factory, org, device_id, admin_user)

    r = await client.post("/api/v1/agent/heartbeat", **_hb(token))
    assert r.status_code == 200, r.text
    assert r.json().get("tasks", []) == []

    # Still claimable the old way.
    claimed = await client.get("/api/v1/agent/tasks?context=system",
                               headers={"Authorization": f"Bearer {token}"})
    assert claimed.status_code == 200
    assert len(claimed.json()) == 1
    assert claimed.json()[0]["action_id"] == "clear_system_temp"


async def test_new_agent_receives_tasks_on_heartbeat(client, session_factory, org, admin_user):
    device_id, token = await _device(session_factory, org, machine="hb-2")
    await _approved_system_task(session_factory, org, device_id, admin_user)

    r = await client.post("/api/v1/agent/heartbeat", **_hb(token, include_tasks=True))
    assert r.status_code == 200, r.text
    tasks = r.json()["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["action_id"] == "clear_system_temp"

    # Claimed exactly once — a second heartbeat must not redeliver it.
    again = await client.post("/api/v1/agent/heartbeat", **_hb(token, include_tasks=True))
    assert again.json()["tasks"] == []


async def test_heartbeat_never_takes_the_trays_user_tasks(client, session_factory, org, admin_user):
    """The Tray is a separate process claiming context=user. If the heartbeat swept those up,
    user-context remediations would be dispatched to a process that cannot run them."""
    device_id, token = await _device(session_factory, org, machine="hb-3")
    async with session_factory() as s:
        device = await s.get(Device, device_id)
        await RemediationService(s).create_task(
            org_id=org.id, device=device, action_id="clear_temp", params=None,
            reason="user-context test", source=RemediationSource.USER, actor_user_id=admin_user.id,
        )

    r = await client.post("/api/v1/agent/heartbeat", **_hb(token, include_tasks=True))
    assert r.json()["tasks"] == []          # not the heartbeat's to take

    tray = await client.get("/api/v1/agent/tasks",   # defaults to context=user
                            headers={"Authorization": f"Bearer {token}"})
    assert len(tray.json()) == 1
    assert tray.json()[0]["action_id"] == "clear_temp"


async def test_heartbeat_still_records_liveness(client, session_factory, org):
    """Whatever else changes, the beat must keep doing its original job."""
    device_id, token = await _device(session_factory, org, machine="hb-4")
    async with session_factory() as s:
        before = (await s.get(Device, device_id)).last_seen_at

    r = await client.post("/api/v1/agent/heartbeat", **_hb(token, include_tasks=True))
    assert r.status_code == 200
    async with session_factory() as s:
        d = await s.get(Device, device_id)
        assert d.last_seen_at >= before
        assert d.agent_version == "0.6.4"
