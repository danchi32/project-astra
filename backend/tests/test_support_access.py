"""E1 — SAVIO support may view a customer's portal only inside a window the customer opened."""
import uuid
from datetime import timedelta

import jwt
from sqlalchemy import select

from app.core.config import get_settings
from app.models import AuditLog, Notification, Organization, User
from app.models.base import utcnow
from app.services.invites import InviteService

_PW = "Password12345"


async def _register(client, sf, org, email):
    async with sf() as s:
        _, code = await InviteService(s).create(note="t", expires_in_days=30)
    r = await client.post("/api/v1/auth/register", json={"terms_accepted": True,
        "invite_code": code, "organization_name": org,
        "admin_name": "A", "admin_email": email, "admin_password": _PW})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _setup(client, sf):
    op = await _register(client, sf, "Op Co", "op@saviops.com")
    async with sf() as s:
        u = (await s.execute(select(User).where(User.email == "op@saviops.com"))).scalar_one()
        u.is_platform_admin = True
        await s.commit()
    cust = await _register(client, sf, "Cust Co", "admin@custco.com")
    async with sf() as s:
        oid = (await s.execute(select(Organization).where(Organization.name == "Cust Co"))).scalar_one().id
    return op, cust, str(oid)


async def _mint(client, op, oid):
    return await client.post(f"/api/v1/platform/organizations/{oid}/view-token", headers=op)


async def _grant(client, cust, hours=1):
    return await client.put("/api/v1/settings/support-access", headers=cust, json={"hours": hours})


async def test_no_window_no_token(client, session_factory):
    op, cust, oid = await _setup(client, session_factory)
    r = await _mint(client, op, oid)
    assert r.status_code == 409
    assert "support access" in r.json()["detail"]
    state = (await client.get("/api/v1/settings/support-access", headers=cust)).json()
    assert state == {"active": False, "until": None}


async def test_grant_mints_token_capped_to_window(client, session_factory):
    op, cust, oid = await _setup(client, session_factory)
    g = await _grant(client, cust, 1)
    assert g.status_code == 200 and g.json()["active"] is True

    r = await _mint(client, op, oid)
    assert r.status_code == 200, r.text
    s = get_settings()
    claims = jwt.decode(r.json()["access_token"], s.jwt_secret_key, algorithms=[s.jwt_algorithm])
    assert claims["exp"] - claims["iat"] <= 3600


async def test_revoke_ends_an_open_session_on_its_next_request(client, session_factory):
    op, cust, oid = await _setup(client, session_factory)
    await _grant(client, cust, 24)
    view = {"Authorization": f"Bearer {(await _mint(client, op, oid)).json()['access_token']}"}
    assert (await client.get("/api/v1/devices", headers=view)).status_code == 200

    assert (await client.delete("/api/v1/settings/support-access", headers=cust)).status_code == 200
    blocked = await client.get("/api/v1/devices", headers=view)
    assert blocked.status_code == 403
    assert "ended" in blocked.json()["detail"]


async def test_expired_window_blocks_the_token_too(client, session_factory):
    op, cust, oid = await _setup(client, session_factory)
    await _grant(client, cust, 1)
    view = {"Authorization": f"Bearer {(await _mint(client, op, oid)).json()['access_token']}"}
    async with session_factory() as s:
        org = await s.get(Organization, uuid.UUID(oid))
        org.support_access_until = utcnow() - timedelta(minutes=1)
        await s.commit()
    assert (await client.get("/api/v1/devices", headers=view)).status_code == 403


async def test_only_short_windows_and_only_admins(client, session_factory):
    _, cust, _ = await _setup(client, session_factory)
    assert (await _grant(client, cust, 720)).status_code == 422
    # A technician can't open the door on the admin's behalf.
    tech = await client.post("/api/v1/users", headers=cust, json={
        "email": "tech@custco.com", "full_name": "T", "password": _PW, "role": "technician"})
    assert tech.status_code in (200, 201), tech.text
    login = await client.post("/api/v1/auth/login", json={"email": "tech@custco.com", "password": _PW})
    th = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert (await _grant(client, th, 1)).status_code == 403


async def test_grant_revoke_and_request_are_in_the_customers_audit_log(client, session_factory):
    op, cust, oid = await _setup(client, session_factory)
    r = await client.post(f"/api/v1/platform/organizations/{oid}/support-access-request",
                          headers=op, json={"reason": "Ticket 42, disk alerts"})
    assert r.status_code == 204, r.text
    await _grant(client, cust, 1)
    await client.delete("/api/v1/settings/support-access", headers=cust)

    org_uuid = uuid.UUID(oid)
    async with session_factory() as s:
        actions = set((await s.execute(
            select(AuditLog.action).where(AuditLog.org_id == org_uuid))).scalars())
        notes = (await s.execute(
            select(Notification).where(Notification.org_id == org_uuid))).scalars().all()
    assert {"support_access.request", "support_access.grant", "support_access.revoke"} <= actions
    assert any("Ticket 42" in n.message for n in notes)


async def test_view_entry_names_the_savio_viewer(client, session_factory):
    """The viewer lives in SAVIO's org, so the customer's audit page can't resolve their id;
    the entry itself has to say who looked."""
    op, cust, oid = await _setup(client, session_factory)
    await _grant(client, cust, 1)
    assert (await _mint(client, op, oid)).status_code == 200
    async with session_factory() as s:
        entry = (await s.execute(select(AuditLog).where(
            AuditLog.org_id == uuid.UUID(oid), AuditLog.action == "platform.view_as"))).scalar_one()
    assert entry.detail["by"] == "op@saviops.com"


async def test_view_as_cannot_extend_its_own_window(client, session_factory):
    """Read-only tokens can't write, so SAVIO can never grant itself more time."""
    op, cust, oid = await _setup(client, session_factory)
    await _grant(client, cust, 1)
    view = {"Authorization": f"Bearer {(await _mint(client, op, oid)).json()['access_token']}"}
    assert (await _grant(client, view, 72)).status_code == 403


async def test_demo_org_needs_no_window(client, session_factory):
    op, _, oid = await _setup(client, session_factory)
    async with session_factory() as s:
        (await s.get(Organization, uuid.UUID(oid))).is_demo = True
        await s.commit()
    assert (await _mint(client, op, oid)).status_code == 200
