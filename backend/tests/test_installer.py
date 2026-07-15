"""Permanent per-org enrollment key: one installer, no token step, no expiry, rotatable."""
from sqlalchemy import select

from app.models import Organization
from app.services.invites import InviteService


def _enroll(client, key, machine_id):
    return client.post("/api/v1/agent/enroll", json={
        "enrollment_token": key, "hostname": machine_id, "machine_id": machine_id,
        "os_version": "Windows 11", "agent_version": "0.1.0"})


async def test_installer_has_permanent_key_and_enrolls(client, admin_headers):
    r = await client.get("/api/v1/devices/installer", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    key = body["enrollment_key"]
    assert key and len(key) > 20
    assert key in body["script"]              # baked into the installer
    assert body["filename"].endswith(".ps1")

    enrolled = await _enroll(client, key, "PC-1")
    assert enrolled.status_code in (200, 201), enrolled.text
    devices = (await client.get("/api/v1/devices", headers=admin_headers)).json()
    assert any(d["hostname"] == "PC-1" for d in devices)


async def test_key_is_stable_across_fetches(client, admin_headers):
    a = (await client.get("/api/v1/devices/installer", headers=admin_headers)).json()["enrollment_key"]
    b = (await client.get("/api/v1/devices/installer", headers=admin_headers)).json()["enrollment_key"]
    assert a == b  # permanent — not regenerated each time


async def test_rotate_invalidates_old_key(client, admin_headers):
    key1 = (await client.get("/api/v1/devices/installer", headers=admin_headers)).json()["enrollment_key"]
    rotated = await client.post("/api/v1/devices/enrollment-key/rotate", headers=admin_headers)
    assert rotated.status_code == 200, rotated.text
    key2 = rotated.json()["enrollment_key"]
    assert key2 != key1

    assert (await _enroll(client, key1, "OLD")).status_code == 401   # old installer dead
    assert (await _enroll(client, key2, "NEW")).status_code in (200, 201)


async def test_installer_requires_admin(client, user_headers):
    assert (await client.get("/api/v1/devices/installer", headers=user_headers)).status_code == 403
    assert (await client.post("/api/v1/devices/enrollment-key/rotate", headers=user_headers)).status_code == 403


async def test_each_org_gets_a_distinct_key(client, session_factory):
    async def reg(org, email):
        async with session_factory() as s:
            _, code = await InviteService(s).create(note="t", expires_in_days=30)
        r = await client.post("/api/v1/auth/register", json={
            "invite_code": code, "organization_name": org, "admin_name": "A",
            "admin_email": email, "admin_password": "Password12345"})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    ha = await reg("Org One", "one@x.com")
    hb = await reg("Org Two", "two@x.com")
    ka = (await client.get("/api/v1/devices/installer", headers=ha)).json()["enrollment_key"]
    kb = (await client.get("/api/v1/devices/installer", headers=hb)).json()["enrollment_key"]
    assert ka and kb and ka != kb

    # A key only enrolls into its own org.
    await _enroll(client, ka, "A1")
    async with session_factory() as s:
        one = (await s.execute(select(Organization).where(Organization.name == "Org One"))).scalar_one()
        two = (await s.execute(select(Organization).where(Organization.name == "Org Two"))).scalar_one()
    from app.repositories.devices import DeviceRepository
    async with session_factory() as s:
        assert len(await DeviceRepository(s).list_by_org(one.id)) == 1
        assert len(await DeviceRepository(s).list_by_org(two.id)) == 0
