"""An unchanged inventory push must not rewrite the tables.

The agent re-sends its full inventory hourly; rewriting ~300 service rows per device per
hour regardless of change is the dominant source of write churn and the real cap on fleet
size. These tests pin the skip behaviour, and — more importantly — that a genuine change
still lands.
"""
from sqlalchemy import func, select

from app.models import Device, DeviceInstalledApp, DeviceService
from app.services.telemetry import _fingerprint

PUSH = {
    "collected_at": "2026-07-30T10:00:00Z",
    "cpu_percent": 20.0,
    "ram_total_mb": 16384,
    "ram_used_mb": 4096,
    "disks": [{"drive": "C:", "total_gb": 500.0, "used_gb": 200.0, "free_gb": 300.0}],
}


def _push(*, services=None, apps=None):
    body = dict(PUSH)
    if services is not None:
        body["services"] = services
    if apps is not None:
        body["installed_apps"] = apps
    return body


SVC_A = [
    {"name": "Spooler", "display_name": "Print Spooler", "status": "Running", "start_type": "Auto"},
    {"name": "Dnscache", "display_name": "DNS Client", "status": "Running", "start_type": "Auto"},
]
APP_A = [{"name": "Chrome", "version": "120.0", "publisher": "Google", "install_date": None}]


async def _enroll(client, admin_headers) -> str:
    key = (await client.get("/api/v1/devices/installer", headers=admin_headers)).json()["enrollment_key"]
    r = await client.post("/api/v1/agent/enroll", json={
        "enrollment_token": key, "hostname": "INV-PC", "machine_id": "inv-1",
        "os_version": "Windows 11", "agent_version": "0.6.4"})
    return r.json()["device_token"]


async def _ingest(client, token, body):
    r = await client.post("/api/v1/agent/telemetry", json=body,
                          headers={"Authorization": f"Bearer {token}"})
    assert r.status_code in (200, 201, 204), r.text
    return r


def test_fingerprint_is_order_independent():
    """The agent may enumerate services in any order; that must not read as a change."""
    class I:
        def __init__(self, n): self.name = n
    assert _fingerprint([I("a"), I("b")], ("name",)) == _fingerprint([I("b"), I("a")], ("name",))
    assert _fingerprint([I("a")], ("name",)) != _fingerprint([I("b")], ("name",))


def test_fingerprint_treats_none_and_empty_string_alike():
    """Known, accepted collision: a missing value and an empty one hash the same. Both mean
    "no value" coming off a Windows inventory, so conflating them can't hide a real change."""
    class I:
        def __init__(self, v): self.name = "x"; self.version = v
    assert _fingerprint([I(None)], ("name", "version")) == _fingerprint([I("")], ("name", "version"))


async def _row_ids(session_factory, model, device_id):
    async with session_factory() as s:
        rows = (await s.execute(select(model.id).where(model.device_id == device_id))).scalars().all()
        return set(rows)


async def test_unchanged_push_does_not_rewrite_rows(client, admin_headers, session_factory):
    token = await _enroll(client, admin_headers)
    await _ingest(client, token, _push(services=SVC_A, apps=APP_A))

    async with session_factory() as s:
        device_id = (await s.execute(select(Device.id).where(Device.machine_id == "inv-1"))).scalar_one()
    first_svc = await _row_ids(session_factory, DeviceService, device_id)
    first_app = await _row_ids(session_factory, DeviceInstalledApp, device_id)
    assert len(first_svc) == 2 and len(first_app) == 1

    # Same inventory again (order shuffled, as a real agent might).
    await _ingest(client, token, _push(services=list(reversed(SVC_A)), apps=APP_A))

    # Identical primary keys ⇒ nothing was deleted and re-inserted.
    assert await _row_ids(session_factory, DeviceService, device_id) == first_svc
    assert await _row_ids(session_factory, DeviceInstalledApp, device_id) == first_app


async def test_changed_push_is_written(client, admin_headers, session_factory):
    """The skip must never swallow a real change — a stopped service has to show up."""
    token = await _enroll(client, admin_headers)
    await _ingest(client, token, _push(services=SVC_A))

    stopped = [dict(SVC_A[0], status="Stopped"), SVC_A[1]]
    await _ingest(client, token, _push(services=stopped))

    async with session_factory() as s:
        rows = (await s.execute(select(DeviceService.name, DeviceService.status))).all()
    assert dict(rows)["Spooler"] == "Stopped"


async def test_first_push_after_upgrade_writes(client, admin_headers, session_factory):
    """Existing devices have NULL hashes, so the first push must be treated as changed."""
    token = await _enroll(client, admin_headers)
    async with session_factory() as s:
        d = (await s.execute(select(Device).where(Device.machine_id == "inv-1"))).scalar_one()
        assert d.services_hash is None       # nothing recorded yet

    await _ingest(client, token, _push(services=SVC_A))
    async with session_factory() as s:
        d = (await s.execute(select(Device).where(Device.machine_id == "inv-1"))).scalar_one()
        assert d.services_hash                # seeded
        count = (await s.execute(
            select(func.count()).select_from(DeviceService).where(DeviceService.device_id == d.id)
        )).scalar_one()
    assert count == 2
