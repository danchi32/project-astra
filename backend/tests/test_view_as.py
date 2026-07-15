"""Super-admin 'view as organization' (read-only drill-in) + platform overview."""
from sqlalchemy import select

from app.models import Organization, User
from app.services.invites import InviteService

_PW = "Password12345"


async def _register(client, sf, org, email):
    async with sf() as s:
        _, code = await InviteService(s).create(note="t", expires_in_days=30)
    return await client.post("/api/v1/auth/register", json={
        "invite_code": code, "organization_name": org,
        "admin_name": "A", "admin_email": email, "admin_password": _PW})


async def _promote(sf, email):
    async with sf() as s:
        u = (await s.execute(select(User).where(User.email == email))).scalar_one()
        u.is_platform_admin = True
        await s.commit()


async def _org_id(sf, name):
    async with sf() as s:
        return str((await s.execute(select(Organization).where(Organization.name == name))).scalar_one().id)


async def _enroll(client, headers, hostname, machine_id):
    tok = (await client.post("/api/v1/devices/enrollment-tokens", headers=headers, json={"name": "f"})).json()["token"]
    return await client.post("/api/v1/agent/enroll", json={
        "enrollment_token": tok, "hostname": hostname, "machine_id": machine_id,
        "os_version": "Windows 11", "agent_version": "0.1.0"})


async def test_platform_overview_aggregates_all_orgs(client, session_factory):
    reg = await _register(client, session_factory, "Ov A", "a@ov.com")
    await _register(client, session_factory, "Ov B", "b@ov.com")
    await _promote(session_factory, "a@ov.com")
    h = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    r = await client.get("/api/v1/platform/overview", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_organizations"] >= 2
    assert body["orgs_by_status"].get("trialing", 0) >= 2
    assert "total_devices" in body and "online_devices" in body


async def test_overview_requires_platform_admin(client, session_factory):
    reg = await _register(client, session_factory, "Nope Co", "n@co.com")
    h = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    assert (await client.get("/api/v1/platform/overview", headers=h)).status_code == 403


async def test_view_as_scopes_to_target_and_is_read_only(client, session_factory):
    admin = await _register(client, session_factory, "Home Co", "home@co.com")
    await _promote(session_factory, "home@co.com")
    ha = {"Authorization": f"Bearer {admin.json()['access_token']}"}
    await _enroll(client, ha, "H-PC", "h1")  # Home Co's own device

    b = await _register(client, session_factory, "Target Co", "t@co.com")
    hb = {"Authorization": f"Bearer {b.json()['access_token']}"}
    await _enroll(client, hb, "T-PC", "t1")  # Target Co's device
    bid = await _org_id(session_factory, "Target Co")

    vt = await client.post(f"/api/v1/platform/organizations/{bid}/view-token", headers=ha)
    assert vt.status_code == 200, vt.text
    assert vt.json()["org_name"] == "Target Co"
    view = {"Authorization": f"Bearer {vt.json()['access_token']}"}

    # Reads return Target Co's data, NOT Home Co's — proves the scope swap.
    devices = await client.get("/api/v1/devices", headers=view)
    assert devices.status_code == 200
    hostnames = {d["hostname"] for d in devices.json()}
    assert "T-PC" in hostnames
    assert "H-PC" not in hostnames

    # Writes are blocked entirely under a view-as token.
    blocked = await client.post("/api/v1/users", headers=view,
        json={"email": "x@t.com", "full_name": "X", "password": _PW, "role": "user"})
    assert blocked.status_code == 403


async def test_view_token_requires_platform_admin(client, session_factory):
    reg = await _register(client, session_factory, "Plain Co", "p@co.com")
    h = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    oid = await _org_id(session_factory, "Plain Co")
    r = await client.post(f"/api/v1/platform/organizations/{oid}/view-token", headers=h)
    assert r.status_code == 403
