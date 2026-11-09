"""L2 — Windows activation and cracked-activation detection."""
from types import SimpleNamespace as Row

from sqlalchemy import select

from app.core.security import hash_opaque_token
from app.models import Device, DeviceInstalledApp, DeviceLicensing, DeviceService
from app.models.base import utcnow
from app.services.licensing import activation_tool_findings, windows_activation


def _win(status=1, channel="Retail", kms=None):
    return Row(kind="windows", license_status=status, channel=channel, kms_host=kms)


def _office(status=5, kms=None):
    return Row(kind="office", license_status=status, channel="Retail", kms_host=kms)


# ── Pure rules ──────────────────────────────────────────────────────────────

def test_activated_windows_passes_with_channel():
    assert windows_activation([_win()]) == ("pass", "Activated (Retail)")


def test_unactivated_windows_fails_in_plain_words():
    assert windows_activation([_win(status=5)]) == ("fail", "Not activated (notification mode)")


def test_no_report_is_unknown_never_a_pass():
    assert windows_activation([])[0] == "unknown"
    assert windows_activation([_win(status=-1)])[0] == "unknown"


def test_office_grace_placeholders_do_not_fail_windows_activation():
    """Microsoft 365 machines carry Office16O365…R_Grace rows in notification mode even when
    properly licensed (seen on a real laptop). They must not make anything fail."""
    assert windows_activation([_win(), _office(status=5)]) == ("pass", "Activated (Retail)")
    assert activation_tool_findings([_win(), _office(status=5)], [], "PC-1") == []


def test_loopback_kms_is_a_crack_even_though_windows_says_licensed():
    rows = [_win(channel="Volume:GVLK", kms="127.0.0.2")]
    assert windows_activation(rows)[0] == "pass"
    assert activation_tool_findings(rows, [], "PC-1") == [
        "Windows activated against KMS host '127.0.0.2'"]


def test_kms_on_the_machine_itself_is_a_crack():
    assert activation_tool_findings([_win(kms="pc-1.corp.local")], [], "PC-1")


def test_public_piracy_kms_is_flagged_but_a_corporate_kms_is_not():
    assert activation_tool_findings([_office(kms="kms8.msguides.com")], [], "PC-1")
    assert activation_tool_findings([_win(kms="kms.acme-corp.com")], [], "PC-1") == []


def test_activator_in_apps_or_services_is_flagged_once():
    found = activation_tool_findings([], ["KMSpico", "KMSpico", "Google Chrome"], "PC-1")
    assert found == ["Activator present: KMSpico"]


# ── Ingest + compliance end to end ──────────────────────────────────────────

async def _enroll(client, admin_headers):
    key = (await client.get("/api/v1/devices/installer", headers=admin_headers)).json()["enrollment_key"]
    r = await client.post("/api/v1/agent/enroll", json={
        "enrollment_token": key, "hostname": "LIC-PC", "machine_id": "lic-1",
        "os_version": "Windows 11", "agent_version": "0.14.0"})
    return r.json()["device_token"]


PUSH = {
    "collected_at": "2026-11-09T10:00:00Z", "cpu_percent": 5.0, "ram_total_mb": 8192,
    "ram_used_mb": 2048, "disks": [{"drive": "C:", "total_gb": 100.0, "used_gb": 20.0, "free_gb": 80.0}],
}


async def _push(client, token, licensing):
    body = dict(PUSH)
    if licensing is not None:
        body["licensing"] = licensing
    r = await client.post("/api/v1/agent/telemetry", json=body,
                          headers={"Authorization": f"Bearer {token}"})
    assert r.status_code in (200, 201, 204), r.text


async def _checks(client, admin_headers):
    rows = (await client.get("/api/v1/compliance/devices", headers=admin_headers)).json()["items"]
    return {c["key"]: c for c in rows[0]["checks"]}


async def test_ingest_replaces_rows_and_none_keeps_them(client, admin_headers, session_factory):
    token = await _enroll(client, admin_headers)
    win = {"kind": "windows", "name": "Windows(R), Professional edition", "license_status": 1,
           "channel": "Retail"}
    await _push(client, token, [win])
    await _push(client, token, None)        # a push between inventories
    async with session_factory() as s:
        rows = (await s.execute(select(DeviceLicensing))).scalars().all()
    assert [(r.kind, r.license_status) for r in rows] == [("windows", 1)]


async def test_compliance_reports_both_checks(client, admin_headers, session_factory):
    token = await _enroll(client, admin_headers)
    await _push(client, token, [{"kind": "windows", "name": "Windows(R), Professional edition",
                                 "license_status": 1, "channel": "Volume:GVLK",
                                 "kms_host": "127.0.0.2"}])
    checks = await _checks(client, admin_headers)
    assert checks["genuine_windows"]["status"] == "pass"
    assert checks["no_activation_tools"]["status"] == "fail"
    assert "127.0.0.2" in checks["no_activation_tools"]["detail"]


async def test_activator_service_fails_without_any_licensing_data(
        client, admin_headers, admin_user, session_factory):
    """Pre-0.14 agents send no licensing, but their service list can still give a crack away."""
    async with session_factory() as s:
        d = Device(org_id=admin_user.org_id, hostname="OLD-PC", machine_id="old-1",
                   os_version="Windows 10", agent_version="0.13.1",
                   token_hash=hash_opaque_token("tok-old"), last_seen_at=utcnow())
        s.add(d)
        await s.flush()
        s.add(DeviceService(org_id=d.org_id, device_id=d.id, name="KMSELDI",
                            display_name="Service KMSELDI", status="Running", start_type="Auto",
                            collected_at=utcnow()))
        s.add(DeviceInstalledApp(org_id=d.org_id, device_id=d.id, name="Google Chrome",
                                 collected_at=utcnow()))
        await s.commit()
    checks = await _checks(client, admin_headers)
    assert checks["genuine_windows"]["status"] == "unknown"
    assert checks["no_activation_tools"]["status"] == "fail"


async def test_unknown_kind_is_rejected(client, admin_headers):
    token = await _enroll(client, admin_headers)
    r = await client.post("/api/v1/agent/telemetry",
                          json=dict(PUSH, licensing=[{"kind": "visio", "name": "x", "license_status": 1}]),
                          headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 422
