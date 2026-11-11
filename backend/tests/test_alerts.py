"""N1 — early-warning alerts: edge-triggered, a real forecast, email for critical ones."""
from datetime import timedelta

from sqlalchemy import select

from app.models import Device, Notification, OrganizationSettings, TelemetrySnapshot
from app.models.base import utcnow
from app.models.telemetry import TelemetryDailyRollup
from app.services.alerts import disk_days_left

# ── the forecast on its own ─────────────────────────────────────────────────

def test_falling_disk_has_days_left():
    # 20 % free, losing 2 %/day → about 10 days from the last point (6 %) is 3 days.
    pts = [(i, 20 - 2 * i) for i in range(8)]
    assert round(disk_days_left(pts)) == 3


def test_flat_or_growing_disk_never_forecasts():
    assert disk_days_left([(i, 30.0) for i in range(10)]) is None
    assert disk_days_left([(i, 30 + i) for i in range(10)]) is None


def test_too_little_history_is_not_a_trend():
    assert disk_days_left([(0, 20), (1, 18), (2, 16)]) is None


# ── through ingest ──────────────────────────────────────────────────────────

BASE = {"cpu_percent": 5.0, "ram_total_mb": 8192, "ram_used_mb": 2048,
        "disks": [{"drive": "C:", "total_gb": 100.0, "used_gb": 50.0, "free_gb": 50.0}]}


def _push(**extra):
    return dict(BASE, collected_at=utcnow().isoformat(), **extra)


def _defender(status):
    return [{"name": "WinDefend", "display_name": "Microsoft Defender Antivirus Service",
             "status": status, "start_type": "Automatic"}]


def _disk(free_pct):
    return [{"drive": "C:", "total_gb": 100.0, "used_gb": 100.0 - free_pct, "free_gb": float(free_pct)}]


async def _enroll(client, admin_headers):
    key = (await client.get("/api/v1/devices/installer", headers=admin_headers)).json()["enrollment_key"]
    r = await client.post("/api/v1/agent/enroll", json={
        "enrollment_token": key, "hostname": "ALERT-PC", "machine_id": "alert-1",
        "os_version": "Windows 11", "agent_version": "0.14.0"})
    return {"Authorization": f"Bearer {r.json()['device_token']}"}


async def _send(client, dev, body):
    r = await client.post("/api/v1/agent/telemetry", json=body, headers=dev)
    assert r.status_code in (200, 201, 204), r.text


async def _titles(session_factory):
    async with session_factory() as s:
        rows = (await s.execute(select(Notification).order_by(Notification.created_at))).scalars().all()
    return [(n.severity.value, n.title) for n in rows if n.category.value == "telemetry"]


async def test_defender_alert_fires_once_and_recovers_once(client, admin_headers, session_factory):
    dev = await _enroll(client, admin_headers)
    await _send(client, dev, _push(services=_defender("Stopped")))
    await _send(client, dev, _push(services=_defender("Stopped")))   # still stopped: no repeat
    await _send(client, dev, _push())                                 # no inventory: no change
    await _send(client, dev, _push(services=_defender("Running")))
    assert await _titles(session_factory) == [
        ("critical", "ALERT-PC: Microsoft Defender not running"),
        ("info", "ALERT-PC: resolved — Microsoft Defender not running"),
    ]


async def test_disk_alert_has_hysteresis(client, admin_headers, session_factory):
    dev = await _enroll(client, admin_headers)
    await _send(client, dev, _push(disks=_disk(9)))    # below 10 → alert
    await _send(client, dev, _push(disks=_disk(11)))   # above 10 but under 12 → stays on
    await _send(client, dev, _push(disks=_disk(13)))   # clears
    titles = await _titles(session_factory)
    assert [t for _, t in titles] == ["ALERT-PC: disk almost full",
                                      "ALERT-PC: resolved — disk almost full"]


async def test_forecast_warns_before_the_disk_is_full(client, admin_headers, session_factory):
    dev = await _enroll(client, admin_headers)
    async with session_factory() as s:
        d = (await s.execute(select(Device).where(Device.machine_id == "alert-1"))).scalar_one()
        today = utcnow().date()
        for i in range(8):  # 30 % → 16 %, falling 2 %/day: ~8 days left at the last point
            s.add(TelemetryDailyRollup(device_id=d.id, org_id=d.org_id, day=today - timedelta(days=8 - i),
                                       samples=10, cpu_avg=5, cpu_max=9, ram_used_avg_mb=1, ram_used_max_mb=1,
                                       disk_free_min_pct=30 - 2 * i))
        await s.commit()
    # Today's push brings the latest point to 14 % → ~7 days left → warning.
    await _send(client, dev, _push(disks=_disk(14), services=_defender("Running")))
    titles = await _titles(session_factory)
    assert ("warning", "ALERT-PC: disk will fill up soon") in titles


async def test_critical_alert_emails_admins_unless_turned_off(
        client, admin_headers, admin_user, session_factory, monkeypatch):
    from app.services import email as email_mod

    sent: list[tuple[str, str]] = []

    async def fake_send(self, *, to, subject, html, **kw):
        sent.append((to, subject))
        return True

    monkeypatch.setattr(email_mod.EmailService, "send", fake_send)
    dev = await _enroll(client, admin_headers)
    await _send(client, dev, _push(services=_defender("Stopped")))
    assert sent == [(admin_user.email, "SAVIO alert: ALERT-PC — Microsoft Defender not running")]

    # Org turns the emails off; the next critical alert is in-app only.
    r = await client.patch("/api/v1/settings/organization", headers=admin_headers,
                           json={"email_critical_alerts": False})
    assert r.status_code == 200 and r.json()["email_critical_alerts"] is False
    sent.clear()
    await _send(client, dev, _push(disks=_disk(3)))
    assert sent == []
    async with session_factory() as s:
        assert (await s.execute(select(OrganizationSettings.email_critical_alerts))).scalar() is False


async def test_a_broken_alerting_path_never_loses_telemetry(client, admin_headers, session_factory, monkeypatch):
    from app.services import alerts

    async def boom(self, **kw):
        raise RuntimeError("alerting bug")

    monkeypatch.setattr(alerts.AlertService, "evaluate", boom)
    dev = await _enroll(client, admin_headers)
    await _send(client, dev, _push(services=_defender("Stopped")))
    async with session_factory() as s:
        assert (await s.execute(select(TelemetrySnapshot))).scalars().first() is not None
