"""J2 Recommendations and J5 Value report.

Recommendations come from live data and follow it: a finding appears, can be dismissed with
a reason, clears when the data clears, and reopens if it comes back. Value counts only fixes
nobody approved, and every number carries its basis.
"""
from datetime import timedelta

from sqlalchemy import select

from app.models import AuditLog, Device, RemediationSource, RemediationStatus, RemediationTask
from app.models.base import utcnow


async def _enroll(client, admin_headers, host):
    key = (await client.get("/api/v1/devices/installer", headers=admin_headers)).json()["enrollment_key"]
    r = (await client.post("/api/v1/agent/enroll", json={
        "enrollment_token": key, "hostname": host, "machine_id": host.lower(),
        "os_version": "Windows 11", "agent_version": "0.15.0"})).json()
    return r["device_id"], {"Authorization": f"Bearer {r['device_token']}"}


async def _push(client, h, *, firewall):
    r = await client.post("/api/v1/agent/telemetry", headers=h, json={
        "collected_at": utcnow().isoformat(), "cpu_percent": 10.0, "ram_total_mb": 8192,
        "ram_used_mb": 4000,
        "disks": [{"drive": "C:", "total_gb": 256.0, "used_gb": 100.0, "free_gb": 156.0}],
        "posture": {"firewall_domain": firewall, "firewall_private": firewall, "firewall_public": firewall}})
    assert r.status_code < 300, r.text


async def _recs(client, headers, status="open"):
    r = await client.get(f"/api/v1/recommendations?status={status}", headers=headers)
    assert r.status_code == 200, r.text
    return {x["key"]: x for x in r.json()}


async def test_recommendation_lifecycle(client, admin_headers, user_headers):
    _, h1 = await _enroll(client, admin_headers, "REC-1")
    _, h2 = await _enroll(client, admin_headers, "REC-2")
    await _push(client, h1, firewall=False)
    await _push(client, h2, firewall=False)

    fw = (await _recs(client, admin_headers))["check:firewall"]
    assert (fw["risk"], fw["effort"], fw["action_id"]) == ("high", "one_click", "enable_firewall")
    assert fw["evidence"]["count"] == 2 and any("REC-1" in d for d in fw["evidence"]["devices"])
    assert (fw["time_minutes"], fw["inr"], fw["basis"]) == (30, None, "2 PCs x 15 min by hand")

    # With the org's own hourly cost, a rupee figure appears, with its working.
    r = await client.patch("/api/v1/settings/organization", headers=admin_headers,
                           json={"it_hourly_cost": 600, "minutes_per_fix": 20})
    assert r.status_code == 200, r.text
    fw = (await _recs(client, admin_headers))["check:firewall"]
    assert (fw["time_minutes"], fw["inr"]) == (40, 400)
    assert fw["basis"] == "2 PCs x 20 min by hand x ₹600/hour"

    # Dismiss needs a reason, is audited, and moves it out of the open list.
    url = f"/api/v1/recommendations/{fw['id']}"
    assert (await client.post(f"{url}/dismiss", headers=user_headers,
                              json={"reason": "managed by GPO"})).status_code == 403
    assert (await client.post(f"{url}/dismiss", headers=admin_headers,
                              json={"reason": ""})).status_code == 422
    r = await client.post(f"{url}/dismiss", headers=admin_headers, json={"reason": "Managed by GPO"})
    assert r.status_code == 200 and r.json()["status"] == "dismissed"
    assert "check:firewall" not in await _recs(client, admin_headers)
    assert (await _recs(client, admin_headers, "dismissed"))["check:firewall"]["dismissed_reason"] == "Managed by GPO"

    # Fixed on both PCs: resolved, and the dismissal ends with it.
    await _push(client, h1, firewall=True)
    await _push(client, h2, firewall=True)
    assert "check:firewall" in await _recs(client, admin_headers, "resolved")
    # Back again on one PC: open, not silently still dismissed.
    await _push(client, h1, firewall=False)
    back = (await _recs(client, admin_headers))["check:firewall"]
    assert back["evidence"]["count"] == 1 and back["dismissed_reason"] is None


async def test_restore_brings_a_dismissal_back(client, admin_headers, session_factory):
    _, h = await _enroll(client, admin_headers, "REC-9")
    await _push(client, h, firewall=False)
    fw = (await _recs(client, admin_headers))["check:firewall"]
    url = f"/api/v1/recommendations/{fw['id']}"
    await client.post(f"{url}/dismiss", headers=admin_headers, json={"reason": "later"})
    assert (await client.post(f"{url}/restore", headers=admin_headers)).json()["status"] == "open"
    assert (await client.post(f"{url}/restore", headers=admin_headers)).status_code == 409
    async with session_factory() as s:
        actions = [a for (a,) in (await s.execute(select(AuditLog.action).where(
            AuditLog.action.like("recommendation.%")))).all()]
    assert sorted(actions) == ["recommendation.dismiss", "recommendation.restore"]


async def test_value_report_counts_only_unattended_fixes(
        client, admin_headers, user_headers, session_factory, admin_user):
    device_id, _ = await _enroll(client, admin_headers, "VAL-1")
    now = utcnow()

    def task(**kw):
        kw.setdefault("completed_at", now - timedelta(days=1))
        return RemediationTask(org_id=admin_user.org_id, device_id=device_id, tier="automatic",
                               reason="t", source=RemediationSource.ASSISTANT,
                               status=RemediationStatus.SUCCEEDED, **kw)

    async with session_factory() as s:
        s.add_all([
            task(action_id="clear_temp", evidence={"verdict": "improved", "recheck": {"held": True}}),
            task(action_id="clear_system_temp", evidence={"verdict": "improved", "recheck": {"held": False}}),
            task(action_id="flush_dns"),
            # A person approved this one: their time, not SAVIO's saving.
            task(action_id="restart_outlook", approved_by_user_id=admin_user.id),
            # Outside the window.
            task(action_id="flush_dns", completed_at=now - timedelta(days=60)),
            # Failed.
            RemediationTask(org_id=admin_user.org_id, device_id=device_id, tier="automatic", reason="t",
                            source=RemediationSource.ASSISTANT, action_id="clear_temp",
                            status=RemediationStatus.FAILED, completed_at=now),
        ])
        await s.commit()

    body = (await client.get("/api/v1/reports/value?days=30", headers=admin_headers)).json()
    assert (body["fixed_unattended"], body["hours_saved"], body["inr_saved"]) == (3, 0.8, None)
    assert (body["proven_improved"], body["held_7_days"], body["came_back"]) == (2, 1, 1)
    assert body["basis"]["hours_saved"] == "3 fixes x 15 min (your setting) / 60"
    assert "inr_saved" not in body["basis"]
    assert {f["action"] for f in body["fixes"]} == {
        "Clear temporary files", "Deep clean system temp", "Flush DNS cache"}

    await client.patch("/api/v1/settings/organization", headers=admin_headers, json={"it_hourly_cost": 800})
    body = (await client.get("/api/v1/reports/value?days=30", headers=admin_headers)).json()
    assert body["inr_saved"] == 600 and body["basis"]["inr_saved"] == "0.8 hours x ₹800/hour (your setting)"

    # Clearing the cost (0) takes the rupee figures away again.
    await client.patch("/api/v1/settings/organization", headers=admin_headers, json={"it_hourly_cost": 0})
    assert (await client.get("/api/v1/reports/value", headers=admin_headers)).json()["inr_saved"] is None
    assert (await client.get("/api/v1/reports/value", headers=user_headers)).status_code == 403
