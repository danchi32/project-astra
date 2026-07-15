"""Invite-only organization registration and cross-tenant isolation.

The isolation test is the important one: two orgs created via registration must
never see each other's users or devices.
"""
from app.services.invites import InviteService

_PW = "Password12345"


async def _issue_invite(session_factory, note: str = "test") -> str:
    async with session_factory() as session:
        _, raw = await InviteService(session).create(note=note, expires_in_days=30)
    return raw


async def _register(client, code: str, org: str, email: str):
    return await client.post(
        "/api/v1/auth/register",
        json={
            "invite_code": code,
            "organization_name": org,
            "admin_name": f"{org} Admin",
            "admin_email": email,
            "admin_password": _PW,
        },
    )


async def test_register_creates_org_and_admin(client, session_factory):
    code = await _issue_invite(session_factory)
    resp = await _register(client, code, "Org A", "admin@orga.com")
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]

    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["role"] == "admin"
    assert me.json()["email"] == "admin@orga.com"


async def test_open_registration_without_invite(client):
    """New customers can self-serve sign up with no invite code."""
    resp = await client.post("/api/v1/auth/register", json={
        "organization_name": "Walk-in Co",
        "admin_name": "Walk In",
        "admin_email": "founder@walkin.com",
        "admin_password": _PW,
    })
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["role"] == "admin"


async def test_bad_and_used_codes_are_rejected(client, session_factory):
    # A supplied invite code, if present, must still be valid — an unknown one fails.
    r = await _register(client, "not-a-real-code", "Nope", "x@nope.com")
    assert r.status_code == 401

    # A code works once, then is spent.
    code = await _issue_invite(session_factory)
    assert (await _register(client, code, "Once", "first@once.com")).status_code == 201
    reused = await _register(client, code, "Twice", "second@twice.com")
    assert reused.status_code == 401, "an invite code must be single-use"


async def test_duplicate_admin_email_rejected(client, session_factory):
    code1 = await _issue_invite(session_factory)
    code2 = await _issue_invite(session_factory)
    assert (await _register(client, code1, "Org1", "dup@x.com")).status_code == 201
    clash = await _register(client, code2, "Org2", "dup@x.com")
    assert clash.status_code == 409


async def test_two_registered_orgs_are_isolated(client, session_factory):
    a = await _register(client, await _issue_invite(session_factory), "Alpha", "admin@alpha.com")
    b = await _register(client, await _issue_invite(session_factory), "Bravo", "admin@bravo.com")
    ha = {"Authorization": f"Bearer {a.json()['access_token']}"}
    hb = {"Authorization": f"Bearer {b.json()['access_token']}"}

    # Each org adds its own user.
    await client.post("/api/v1/users", headers=ha, json={
        "email": "u1@alpha.com", "full_name": "U1", "password": _PW, "role": "user"})
    await client.post("/api/v1/users", headers=hb, json={
        "email": "u2@bravo.com", "full_name": "U2", "password": _PW, "role": "user"})

    # Alpha sees only Alpha users; Bravo's are invisible.
    emails_a = {u["email"] for u in (await client.get("/api/v1/users", headers=ha)).json()}
    assert "u1@alpha.com" in emails_a
    assert "admin@alpha.com" in emails_a
    assert "u2@bravo.com" not in emails_a
    assert "admin@bravo.com" not in emails_a

    # Devices: enroll one into Alpha; Bravo's device list stays empty.
    tok = await client.post("/api/v1/devices/enrollment-tokens", headers=ha, json={"name": "a-fleet"})
    await client.post("/api/v1/agent/enroll", json={
        "enrollment_token": tok.json()["token"], "hostname": "ALPHA-PC",
        "machine_id": "alpha-1", "os_version": "Windows 11", "agent_version": "0.1.0"})

    devices_a = (await client.get("/api/v1/devices", headers=ha)).json()
    devices_b = (await client.get("/api/v1/devices", headers=hb)).json()
    assert any(d["hostname"] == "ALPHA-PC" for d in devices_a)
    assert all(d["hostname"] != "ALPHA-PC" for d in devices_b)

    # Bravo cannot use Alpha's enrollment token from its own list either.
    tokens_b = (await client.get("/api/v1/devices/enrollment-tokens", headers=hb)).json()
    assert all(t["name"] != "a-fleet" for t in tokens_b)
