"""C1 · Proof-of-Fix: the number a fix was for, before it ran, after, and a week later.

Driven through the agent's own endpoints (claim, result, telemetry), because that is where
the readings come from: before at claim, after from the first push following the result,
the recheck from the first push a week on.
"""
from datetime import timedelta

from app.core.security import hash_opaque_token
from app.models import Device, RemediationSource, RemediationTask
from app.models.base import utcnow
from app.services.remediation.evidence import held, verdict, SYSTEM_DISK_FREE, FIREWALL_ON
from app.services.remediation.service import RemediationService


async def _device(session_factory, org, machine):
    async with session_factory() as s:
        d = Device(org_id=org.id, hostname=machine.upper(), machine_id=machine,
                   os_version="Windows 11", agent_version="0.15.0",
                   token_hash=hash_opaque_token(f"tok-{machine}"), last_seen_at=utcnow())
        s.add(d)
        await s.commit()
        return d.id, {"Authorization": f"Bearer tok-{machine}"}


def _push(free_gb, *, at=None, firewall=None):
    body = {
        "collected_at": (at or utcnow()).isoformat(),
        "cpu_percent": 20.0, "ram_total_mb": 16384, "ram_used_mb": 8000,
        "disks": [{"drive": "C:", "total_gb": 500.0, "used_gb": 500.0 - free_gb, "free_gb": free_gb}],
    }
    if firewall is not None:
        body["posture"] = {"firewall_domain": firewall, "firewall_private": firewall,
                           "firewall_public": firewall}
    return body


async def _task(session_factory, org, admin_user, device_id, action_id, **kw):
    async with session_factory() as s:
        device = await s.get(Device, device_id)
        task = await RemediationService(s).create_task(
            org_id=org.id, device=device, action_id=action_id, params=kw.get("params"),
            reason="proof test", source=RemediationSource.USER, actor_user_id=admin_user.id,
            approver=admin_user,
        )
        return task.id


async def _evidence(session_factory, task_id):
    async with session_factory() as s:
        return (await s.get(RemediationTask, task_id)).evidence


async def _run(client, h, task_id, context=""):
    await client.get(f"/api/v1/agent/tasks{context}", headers=h)
    r = await client.post(f"/api/v1/agent/tasks/{task_id}/result", headers=h,
                          json={"success": True, "output": "done"})
    assert r.status_code == 204, r.text


async def test_clean_up_is_proved_by_free_space(client, session_factory, org, admin_user):
    device_id, h = await _device(session_factory, org, "proof-1")
    await client.post("/api/v1/agent/telemetry", headers=h, json=_push(12.0))
    task_id = await _task(session_factory, org, admin_user, device_id, "clear_temp")

    await _run(client, h, task_id)
    ev = await _evidence(session_factory, task_id)
    assert ev["metric"] == "system_disk_free_gb" and ev["before"] == 12.0
    assert "after" not in ev  # nothing has been measured since the fix yet

    await client.post("/api/v1/agent/telemetry", headers=h, json=_push(15.4))
    ev = await _evidence(session_factory, task_id)
    assert (ev["after"], ev["verdict"]) == (15.4, "improved")

    # The portal reads it straight off the task.
    from tests.conftest import ADMIN_PASSWORD, auth_headers
    admin = await auth_headers(client, admin_user.email, ADMIN_PASSWORD)
    rows = (await client.get("/api/v1/remediations", headers=admin)).json()
    rows = rows["items"] if isinstance(rows, dict) else rows
    assert next(t for t in rows if t["id"] == str(task_id))["evidence"]["verdict"] == "improved"


async def test_a_push_collected_before_the_fix_is_not_the_after(client, session_factory, org, admin_user):
    """The agent queues pushes while offline. One collected before the fix ran, delivered
    after, must not be read as the result."""
    device_id, h = await _device(session_factory, org, "proof-2")
    await client.post("/api/v1/agent/telemetry", headers=h, json=_push(12.0))
    task_id = await _task(session_factory, org, admin_user, device_id, "clear_temp")
    await _run(client, h, task_id)

    await client.post("/api/v1/agent/telemetry", headers=h,
                      json=_push(12.0, at=utcnow() - timedelta(minutes=10)))
    assert "after" not in await _evidence(session_factory, task_id)


async def test_firewall_fix_is_proved_by_posture(client, session_factory, org, admin_user):
    device_id, h = await _device(session_factory, org, "proof-3")
    await client.post("/api/v1/agent/telemetry", headers=h, json=_push(50.0, firewall=False))
    task_id = await _task(session_factory, org, admin_user, device_id, "enable_firewall")
    await _run(client, h, task_id, "?context=system")

    # A push without posture can't answer it, so the task keeps waiting.
    await client.post("/api/v1/agent/telemetry", headers=h, json=_push(50.0))
    assert "after" not in await _evidence(session_factory, task_id)

    await client.post("/api/v1/agent/telemetry", headers=h, json=_push(50.0, firewall=True))
    ev = await _evidence(session_factory, task_id)
    assert (ev["before"], ev["after"], ev["verdict"]) == (False, True, "improved")


async def test_seven_day_recheck_catches_a_comeback(client, session_factory, org, admin_user):
    device_id, h = await _device(session_factory, org, "proof-4")
    await client.post("/api/v1/agent/telemetry", headers=h, json=_push(12.0))
    task_id = await _task(session_factory, org, admin_user, device_id, "clear_temp")
    await _run(client, h, task_id)
    await client.post("/api/v1/agent/telemetry", headers=h, json=_push(16.0))

    # Not yet a week: no recheck.
    await client.post("/api/v1/agent/telemetry", headers=h, json=_push(9.0))
    assert "recheck" not in await _evidence(session_factory, task_id)

    async with session_factory() as s:
        t = await s.get(RemediationTask, task_id)
        t.completed_at = utcnow() - timedelta(days=8)
        await s.commit()
    await client.post("/api/v1/agent/telemetry", headers=h, json=_push(9.0))
    ev = await _evidence(session_factory, task_id)
    assert ev["recheck"]["value"] == 9.0 and ev["recheck"]["held"] is False
    assert ev["verdict"] == "improved"  # the first reading stands; the recheck is its own fact


async def test_a_fix_with_nothing_to_measure_claims_nothing(client, session_factory, org, admin_user):
    device_id, h = await _device(session_factory, org, "proof-5")
    await client.post("/api/v1/agent/telemetry", headers=h, json=_push(12.0))
    task_id = await _task(session_factory, org, admin_user, device_id, "flush_dns")
    await _run(client, h, task_id)
    await client.post("/api/v1/agent/telemetry", headers=h, json=_push(12.0))
    assert await _evidence(session_factory, task_id) is None


async def test_no_reading_before_means_unmeasured(client, session_factory, org, admin_user):
    device_id, h = await _device(session_factory, org, "proof-6")  # never pushed telemetry
    task_id = await _task(session_factory, org, admin_user, device_id, "clear_temp")
    await _run(client, h, task_id)
    await client.post("/api/v1/agent/telemetry", headers=h, json=_push(30.0))
    ev = await _evidence(session_factory, task_id)
    assert ev["before"] is None and ev["verdict"] == "unmeasured"


def test_verdicts():
    assert verdict(SYSTEM_DISK_FREE, 10.0, 10.05) == "unchanged"  # noise
    assert verdict(SYSTEM_DISK_FREE, 10.0, 8.0) == "worse"
    assert verdict(FIREWALL_ON, True, True) == "unchanged"
    assert verdict(FIREWALL_ON, False, False) == "unchanged"
    assert verdict(FIREWALL_ON, True, False) == "worse"
    assert verdict(FIREWALL_ON, None, True) == "unmeasured"
    assert held(SYSTEM_DISK_FREE, 10.0, 10.0) is True
    assert held(FIREWALL_ON, False, False) is False
