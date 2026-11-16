"""C2 · Canary rollout: one device, then 10%, then the rest, with a health gate between.

Driven through the real endpoints: the push, the agent claiming and reporting, telemetry
pushes (which carry Critical events and end the soak), halt and resume.
"""
from datetime import timedelta

from sqlalchemy import select, update

from app.models import AuditLog, Deployment, Device, RemediationStatus, RemediationTask
from app.models.base import utcnow
from app.services.deployments import WAVE_SOAK, plan_waves


async def _fleet(client, admin_headers, n, prefix="PC"):
    key = (await client.get("/api/v1/devices/installer", headers=admin_headers)).json()["enrollment_key"]
    out = []
    for i in range(n):
        r = (await client.post("/api/v1/agent/enroll", json={
            "enrollment_token": key, "hostname": f"{prefix}-{i:02d}", "machine_id": f"{prefix}-{i}",
            "os_version": "Windows 11", "agent_version": "0.15.0"})).json()
        out.append((r["device_id"], {"Authorization": f"Bearer {r['device_token']}"}))
    return out


async def _push(client, admin_headers, ids, **kw):
    r = await client.post("/api/v1/deployments/install", headers=admin_headers, json={
        "package_id": "Google.Chrome", "device_ids": ids, "reason": "standard browser", **kw})
    assert r.status_code == 201, r.text
    return r.json()


async def _tasks(session_factory, dep_id):
    async with session_factory() as s:
        return (await s.execute(select(RemediationTask).where(
            RemediationTask.deployment_id == dep_id))).scalars().all()


async def _finish(client, session_factory, fleet, dep_id, *, success=True):
    """Every queued task's device claims and reports; then the soak is wound back."""
    by_id = dict(fleet)
    for t in await _tasks(session_factory, dep_id):
        if t.status is RemediationStatus.APPROVED:
            h = by_id[str(t.device_id)]
            await client.get("/api/v1/agent/tasks?context=system", headers=h)
            await client.post(f"/api/v1/agent/tasks/{t.id}/result", headers=h,
                              json={"success": success, "output": "ok" if success else "winget failed"})
    async with session_factory() as s:
        await s.execute(update(RemediationTask).where(RemediationTask.deployment_id == dep_id)
                        .values(completed_at=utcnow() - WAVE_SOAK - timedelta(minutes=1)))
        await s.commit()


async def _telemetry(client, h, events=()):
    body = {"collected_at": utcnow().isoformat(), "cpu_percent": 10.0, "ram_total_mb": 8192,
            "ram_used_mb": 4000, "disks": []}
    if events:
        body["event_logs"] = list(events)
    r = await client.post("/api/v1/agent/telemetry", headers=h, json=body)
    assert r.status_code < 300, r.text


async def _dep(session_factory, dep_id):
    async with session_factory() as s:
        return await s.get(Deployment, dep_id)


def test_wave_plan():
    fake = [Device(hostname=f"H{i:02d}", last_seen_at=None) for i in range(25)]
    assert [len(w) for w in plan_waves(fake)] == [1, 3, 21]
    assert [len(w) for w in plan_waves(fake[:2])] == [1, 1]
    assert [len(w) for w in plan_waves(fake[:1])] == [1]
    fake[7].last_seen_at = utcnow()            # the online one goes first
    assert plan_waves(fake)[0][0].hostname == "H07"


async def test_waves_open_one_after_another(client, admin_headers, session_factory):
    fleet = await _fleet(client, admin_headers, 12)
    body = await _push(client, admin_headers, [d for d, _ in fleet])
    assert (body["queued"], body["waiting"], body["waves_total"], body["current_wave"]) == (1, 11, 3, 1)
    assert len(await _tasks(session_factory, body["id"])) == 1   # later waves: nothing queued

    # The soak isn't over yet: finishing the canary alone does not open wave 2.
    canary = (await _tasks(session_factory, body["id"]))[0]
    h = dict(fleet)[str(canary.device_id)]
    await client.get("/api/v1/agent/tasks?context=system", headers=h)
    await client.post(f"/api/v1/agent/tasks/{canary.id}/result", headers=h,
                      json={"success": True, "output": "ok"})
    assert len(await _tasks(session_factory, body["id"])) == 1

    # Soak over: the canary's next telemetry push opens wave 2 (10% of 12 = 2 devices).
    await _finish(client, session_factory, fleet, body["id"])
    await _telemetry(client, h)
    assert len(await _tasks(session_factory, body["id"])) == 3
    assert (await _dep(session_factory, body["id"])).current_wave == 1

    await _finish(client, session_factory, fleet, body["id"])
    await _telemetry(client, h)
    tasks = await _tasks(session_factory, body["id"])
    assert len(tasks) == 12

    detail = (await client.get(f"/api/v1/deployments/{body['id']}", headers=admin_headers)).json()
    assert (detail["current_wave"], detail["waiting"], detail["halted_at"]) == (3, 0, None)


async def test_a_failure_halts_the_rollout(client, admin_headers, session_factory):
    fleet = await _fleet(client, admin_headers, 12, prefix="FAIL")
    body = await _push(client, admin_headers, [d for d, _ in fleet])
    await _finish(client, session_factory, fleet, body["id"], success=False)

    dep = await _dep(session_factory, body["id"])
    assert dep.halted_at is not None and "failed on FAIL-" in dep.halt_reason
    for _, h in fleet:
        await _telemetry(client, h)
    assert len(await _tasks(session_factory, body["id"])) == 1   # wave 2 never created

    async with session_factory() as s:
        halt = (await s.execute(select(AuditLog).where(AuditLog.action == "deployment.halt"))).scalars().one()
    assert halt.detail["automatic"] is True


async def test_a_critical_event_halts_and_cancels_queued_installs(client, admin_headers, session_factory):
    fleet = await _fleet(client, admin_headers, 12, prefix="CRIT")
    body = await _push(client, admin_headers, [d for d, _ in fleet])
    await _finish(client, session_factory, fleet, body["id"])
    canary = (await _tasks(session_factory, body["id"]))[0]
    h = dict(fleet)[str(canary.device_id)]
    await _telemetry(client, h)                       # opens wave 2
    assert len(await _tasks(session_factory, body["id"])) == 3

    # A wave-2 device blue-screens before anyone has claimed its install.
    wave2 = [t for t in await _tasks(session_factory, body["id"]) if t.id != canary.id]
    h2 = dict(fleet)[str(wave2[0].device_id)]
    await _telemetry(client, h2, events=[{
        "log_name": "System", "source": "Kernel-Power", "event_id": 41, "level": "Critical",
        "message": "The system has rebooted without cleanly shutting down first.",
        "occurred_at": utcnow().isoformat()}])

    dep = await _dep(session_factory, body["id"])
    assert dep.halted_at is not None and "Critical event" in dep.halt_reason
    statuses = {t.id: t.status for t in await _tasks(session_factory, body["id"])}
    assert all(statuses[t.id] is RemediationStatus.REJECTED for t in wave2)


async def test_halt_and_resume_by_hand(client, admin_headers, user_headers, session_factory):
    fleet = await _fleet(client, admin_headers, 12, prefix="HAND")
    body = await _push(client, admin_headers, [d for d, _ in fleet])
    url = f"/api/v1/deployments/{body['id']}"

    assert (await client.post(f"{url}/halt", headers=user_headers,
                              json={"reason": "wait"})).status_code == 403
    r = await client.post(f"{url}/halt", headers=admin_headers, json={"reason": "vendor recall"})
    assert r.status_code == 200 and "vendor recall" in r.json()["halt_reason"]
    assert [t.status for t in await _tasks(session_factory, body["id"])] == [RemediationStatus.REJECTED]
    assert (await client.post(f"{url}/halt", headers=admin_headers,
                              json={"reason": "again"})).status_code == 409

    r = await client.post(f"{url}/resume", headers=admin_headers)
    assert r.status_code == 200 and r.json()["halted_at"] is None and r.json()["current_wave"] == 2
    assert len(await _tasks(session_factory, body["id"])) == 3   # wave 2 released by the person


async def test_one_device_push_is_one_wave(client, admin_headers, session_factory):
    fleet = await _fleet(client, admin_headers, 1, prefix="ONE")
    body = await _push(client, admin_headers, [fleet[0][0]])
    assert (body["queued"], body["waves_total"]) == (1, None)
