"""L1 — the Free IT Health Check report."""
from datetime import date, timedelta

from app.core.security import hash_opaque_token
from app.models import Asset, Device, DeviceInstalledApp, DeviceService, DeviceWindowsUpdate
from app.models.alert_state import AlertState
from app.models.base import utcnow
from app.models.telemetry import TelemetryDailyRollup


async def _seed(session_factory, org_id):
    async with session_factory() as s:
        now = utcnow()
        old = Device(org_id=org_id, hostname="RECEPTION-PC", machine_id="hc-1", os_version="Windows 10",
                     agent_version="0.14.0", token_hash=hash_opaque_token("hc1"), last_seen_at=now,
                     bios_release_date="2018-03-01")
        new = Device(org_id=org_id, hostname="ASHA-LAPTOP", machine_id="hc-2", os_version="Windows 11",
                     agent_version="0.14.0", token_hash=hash_opaque_token("hc2"), last_seen_at=now,
                     bios_release_date="2025-06-01")
        s.add_all([old, new])
        await s.flush()
        s.add_all([
            DeviceService(org_id=org_id, device_id=old.id, name="WinDefend", display_name="Defender",
                          status="Stopped", start_type="Auto", collected_at=now),
            DeviceService(org_id=org_id, device_id=new.id, name="WinDefend", display_name="Defender",
                          status="Running", start_type="Auto", collected_at=now),
            DeviceWindowsUpdate(org_id=org_id, device_id=old.id, kb_article_id="KB1", title="CU",
                                state="pending", collected_at=now),
            DeviceInstalledApp(org_id=org_id, device_id=new.id, name="ChatGPT", scope="user",
                               user_name="ACME\\asha", collected_at=now),
            DeviceInstalledApp(org_id=org_id, device_id=new.id, name="Janitor Pro", collected_at=now),
            AlertState(org_id=org_id, device_id=old.id, check_key="disk_forecast", state="alerting",
                       since=now, detail="full in ~5 days"),
            Asset(org_id=org_id, name="Asha's laptop", device_id=new.id,
                  warranty_expiry=(date.today() + timedelta(days=30)).isoformat()),
            TelemetryDailyRollup(device_id=new.id, org_id=org_id, day=date.today() - timedelta(days=3),
                                 samples=1, cpu_avg=1, cpu_max=1, ram_used_avg_mb=1, ram_used_max_mb=1),
        ])
        await s.commit()


async def test_report_names_real_problems(client, admin_headers, admin_user, session_factory):
    await _seed(session_factory, admin_user.org_id)
    r = await client.get("/api/v1/reports/health-check", headers=admin_headers)
    assert r.status_code == 200, r.text
    rep = r.json()

    assert rep["devices"] == 2
    assert (rep["days_of_data"], rep["complete"]) == (4, False)          # 4 of 7 days so far
    keys = [f["key"] for f in rep["findings"]]
    assert "defender" in keys and "patch" in keys
    defender = next(f for f in rep["findings"] if f["key"] == "defender")
    assert defender["severity"] == "high" and defender["devices"][0].startswith("RECEPTION-PC")
    # Owner-facing advice, not Fleet Issues' note about what the agent can't push yet.
    assert "Windows Security" in defender["advice"] and "elevated agent" not in defender["advice"]
    # Worst first: high-severity findings lead.
    assert rep["findings"][0]["severity"] == "high"

    assert rep["disks_filling_soon"] == ["RECEPTION-PC"]
    assert rep["old_hardware"] == ["RECEPTION-PC (2018)"]
    assert rep["warranty"][0]["asset"] == "Asha's laptop" and rep["warranty"][0]["expired"] is False
    assert rep["software"]["per_user_installs"] == 1
    # "ChatGPT" is an AI tool; "Janitor Pro" is not a match for "jan".
    assert rep["software"]["ai_tools"] == [{"name": "ChatGPT", "devices": 1}]
    assert rep["per_device"][0]["hostname"] == "RECEPTION-PC"           # lowest score first
    assert "Microsoft Defender not running" in rep["per_device"][0]["failed"]


async def test_empty_org_and_permissions(client, admin_headers, user_headers):
    rep = (await client.get("/api/v1/reports/health-check", headers=admin_headers)).json()
    assert rep["devices"] == 0 and rep["findings"] == [] and rep["days_of_data"] == 0
    assert (await client.get("/api/v1/reports/health-check", headers=user_headers)).status_code == 403
