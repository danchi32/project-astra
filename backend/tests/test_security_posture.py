"""2a Security Score — real Defender / Firewall / BitLocker state, weighted per device."""
from datetime import UTC, datetime

from app.services.compliance import CHECKS, DEFENDER_SIG_MAX_DAYS, WEIGHTS

PUSH = {
    "collected_at": datetime.now(UTC).isoformat(), "cpu_percent": 5.0, "ram_total_mb": 8192,
    "ram_used_mb": 2048, "disks": [{"drive": "C:", "total_gb": 100.0, "used_gb": 20.0, "free_gb": 80.0}],
}
GOOD = {
    "defender_realtime": True, "defender_signature_age_days": 1,
    "firewall_domain": True, "firewall_private": True, "firewall_public": True,
    "bitlocker_os_drive": True,
}


async def _enroll(client, admin_headers, machine="sp-1"):
    key = (await client.get("/api/v1/devices/installer", headers=admin_headers)).json()["enrollment_key"]
    r = await client.post("/api/v1/agent/enroll", json={
        "enrollment_token": key, "hostname": "SP-PC", "machine_id": machine,
        "os_version": "Windows 11", "agent_version": "0.15.0"})
    return r.json()["device_token"]


async def _push(client, token, posture=None):
    body = dict(PUSH)
    if posture is not None:
        body["posture"] = posture
    r = await client.post("/api/v1/agent/telemetry", json=body,
                          headers={"Authorization": f"Bearer {token}"})
    assert r.status_code in (200, 201, 204), r.text


async def _device(client, admin_headers):
    rows = (await client.get("/api/v1/compliance/devices", headers=admin_headers)).json()["items"]
    return rows[0]


def _check(row, key):
    return next(c for c in row["checks"] if c["key"] == key)


def test_every_weighted_check_exists():
    keys = {k for k, _, _ in CHECKS}
    assert set(WEIGHTS) <= keys
    assert WEIGHTS["defender"] > WEIGHTS["disk"]          # an unprotected PC outranks a full disk


async def test_real_time_off_fails_on_the_next_report(client, admin_headers):
    token = await _enroll(client, admin_headers)
    await _push(client, token, GOOD)
    assert _check(await _device(client, admin_headers), "defender")["status"] == "pass"

    await _push(client, token, dict(GOOD, defender_realtime=False))
    row = await _device(client, admin_headers)
    assert _check(row, "defender") == {**_check(row, "defender"), "status": "fail",
                                       "detail": "Real-time protection is off"}
    assert row["status"] != "compliant"


async def test_stale_signatures_fail_even_with_real_time_on(client, admin_headers):
    token = await _enroll(client, admin_headers)
    await _push(client, token, dict(GOOD, defender_signature_age_days=DEFENDER_SIG_MAX_DAYS + 3))
    c = _check(await _device(client, admin_headers), "defender")
    assert c["status"] == "fail" and "days old" in c["detail"]


async def test_firewall_names_the_profile_that_is_off(client, admin_headers):
    token = await _enroll(client, admin_headers)
    await _push(client, token, dict(GOOD, firewall_public=False))
    c = _check(await _device(client, admin_headers), "firewall")
    assert c["status"] == "fail" and "public" in c["detail"]


async def test_bitlocker_state_is_a_real_check(client, admin_headers):
    token = await _enroll(client, admin_headers)
    await _push(client, token, dict(GOOD, bitlocker_os_drive=False))
    assert _check(await _device(client, admin_headers), "bitlocker")["status"] == "fail"
    await _push(client, token, dict(GOOD, bitlocker_os_drive=None))
    assert _check(await _device(client, admin_headers), "bitlocker")["status"] == "unknown"


async def test_weighted_score_counts_a_defender_failure_more_than_a_disk(client, admin_headers):
    token = await _enroll(client, admin_headers)
    await _push(client, token, dict(GOOD, defender_realtime=False))
    row = await _device(client, admin_headers)
    assert row["security_score"] is not None and row["security_score"] < 100
    # Defender (weight 3) is the only failure: the score is the passed weight over the known
    # weight, not a plain pass count.
    known = [c for c in row["checks"] if c["status"] in ("pass", "fail")]
    total_w = sum(WEIGHTS.get(c["key"], 1) for c in known)
    passed_w = sum(WEIGHTS.get(c["key"], 1) for c in known if c["status"] == "pass")
    assert row["security_score"] == round(passed_w / total_w * 100)


async def test_old_agent_without_posture_keeps_service_checks(client, admin_headers):
    token = await _enroll(client, admin_headers, machine="sp-old")
    await _push(client, token, None)                     # agent 0.14: no posture block
    row = await _device(client, admin_headers)
    assert _check(row, "bitlocker")["status"] == "unknown"
    # No service rows were reported either, so Defender is unknown, as before this module.
    assert _check(row, "defender")["status"] == "unknown"


async def test_fleet_security_score_is_the_mean_of_devices(client, admin_headers):
    t1 = await _enroll(client, admin_headers, machine="sp-a")
    await _push(client, t1, GOOD)
    # agent_reporting reads the heartbeat, not telemetry.
    await client.post("/api/v1/agent/heartbeat", json={"agent_version": "0.15.0"},
                      headers={"Authorization": f"Bearer {t1}"})
    summary = (await client.get("/api/v1/compliance/summary", headers=admin_headers)).json()
    row = await _device(client, admin_headers)
    assert summary["security_score"] == 100, [(c["key"], c["status"]) for c in row["checks"] if c["status"] != "pass"]
