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


async def _apps(session_factory):
    async with session_factory() as s:
        return (await s.execute(
            select(DeviceInstalledApp.name, DeviceInstalledApp.scope, DeviceInstalledApp.user_name)
        )).all()


async def test_pre_014_agent_apps_are_machine_scope(client, admin_headers, session_factory):
    """Older agents send neither scope nor user_name; that must still ingest, as machine-wide."""
    token = await _enroll(client, admin_headers)
    await _ingest(client, token, _push(apps=APP_A))
    assert await _apps(session_factory) == [("Chrome", "machine", None)]


async def test_per_user_installs_are_kept_per_person(client, admin_headers, session_factory):
    """The same app installed for two people is two installs, and a machine-wide copy is a
    third — uninstalling one leaves the others, so none may be collapsed into another."""
    token = await _enroll(client, admin_headers)
    apps = [
        {"name": "ChatGPT", "version": "1.0", "publisher": "OpenAI", "scope": "user", "user_name": "ACME\asha"},
        {"name": "ChatGPT", "version": "1.0", "publisher": "OpenAI", "scope": "user", "user_name": "ACME\ravi"},
        {"name": "Chrome", "version": "120.0", "publisher": "Google", "scope": "machine"},
    ]
    await _ingest(client, token, _push(apps=apps))
    assert sorted(await _apps(session_factory)) == [
        ("ChatGPT", "user", "ACME\asha"),
        ("ChatGPT", "user", "ACME\ravi"),
        ("Chrome", "machine", None),
    ]


async def test_new_user_install_counts_as_a_change(client, admin_headers, session_factory):
    """A second person installing the same app must not be skipped as 'unchanged'."""
    token = await _enroll(client, admin_headers)
    one = [{"name": "Zoom", "version": "6.0", "publisher": "Zoom", "scope": "user", "user_name": "ACME\asha"}]
    await _ingest(client, token, _push(apps=one))
    two = one + [dict(one[0], user_name="ACME\ravi")]
    await _ingest(client, token, _push(apps=two))
    assert len(await _apps(session_factory)) == 2


async def test_unknown_scope_is_rejected(client, admin_headers):
    token = await _enroll(client, admin_headers)
    r = await client.post("/api/v1/agent/telemetry", json=_push(apps=[dict(APP_A[0], scope="global")]),
                          headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 422
