from app.core.security import hash_opaque_token
from app.models import Device, DeviceInstalledApp, DeviceWindowsUpdate
from app.models.base import utcnow


class _Org:
    """Minimal stand-in carrying just the org id our seed helper needs."""

    def __init__(self, org_id):
        self.id = org_id


async def _make_device(session_factory, org, hostname="LSI-COMP", machine="mach-comp"):
    """Seed one device with a pending update and uTorrent installed."""
    async with session_factory() as session:
        device = Device(
            org_id=org.id, hostname=hostname, machine_id=machine,
            os_version="Windows 11", agent_version="0.6.4",
            token_hash=hash_opaque_token(f"tok-{machine}"), last_seen_at=utcnow(),
        )
        session.add(device)
        await session.flush()
        session.add(DeviceWindowsUpdate(
            org_id=org.id, device_id=device.id, kb_article_id="KB5040442",
            title="Cumulative Update", is_installed=False, collected_at=utcnow(),
        ))
        session.add(DeviceInstalledApp(
            org_id=org.id, device_id=device.id, name="uTorrent", collected_at=utcnow(),
        ))
        await session.commit()
        return device.id


async def test_summary_empty_org(client, admin_headers):
    resp = await client.get("/api/v1/compliance/summary", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_devices"] == 0
    assert body["score"] == 100


async def test_device_fails_patch_check(client, admin_headers, admin_user, session_factory):
    await _make_device(session_factory, _Org(admin_user.org_id))
    resp = await client.get("/api/v1/compliance/devices", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert len(rows) == 1
    patch = next(c for c in rows[0]["checks"] if c["key"] == "patch")
    assert patch["status"] == "fail"
    assert patch["fix_action_id"] == "windows_update_install"


async def test_banned_software_crud_and_detection(client, admin_headers, admin_user, session_factory):
    await _make_device(session_factory, _Org(admin_user.org_id))

    add = await client.post(
        "/api/v1/compliance/banned-software", json={"name": "uTorrent"}, headers=admin_headers)
    assert add.status_code == 201, add.text
    banned_id = add.json()["id"]

    dup = await client.post(
        "/api/v1/compliance/banned-software", json={"name": "utorrent"}, headers=admin_headers)
    assert dup.status_code == 409

    rows = (await client.get("/api/v1/compliance/devices", headers=admin_headers)).json()
    chk = next(c for c in rows[0]["checks"] if c["key"] == "no_banned_software")
    assert chk["status"] == "fail"
    assert "uTorrent" in chk["detail"]

    rm = await client.delete(
        f"/api/v1/compliance/banned-software/{banned_id}", headers=admin_headers)
    assert rm.status_code == 204
    rows = (await client.get("/api/v1/compliance/devices", headers=admin_headers)).json()
    assert all(c["key"] != "no_banned_software" for c in rows[0]["checks"])


async def test_banned_software_add_requires_admin(client, user_headers):
    resp = await client.post(
        "/api/v1/compliance/banned-software", json={"name": "Steam"}, headers=user_headers)
    assert resp.status_code == 403


async def test_compliance_requires_staff(client, user_headers):
    resp = await client.get("/api/v1/compliance/summary", headers=user_headers)
    assert resp.status_code == 403
