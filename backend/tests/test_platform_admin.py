"""Phase A: platform-operator (super-admin) console + 14-day trial -> read-only."""
from datetime import timedelta

from sqlalchemy import select

from app.models import Organization, SubscriptionStatus, User
from app.models.base import as_utc, utcnow
from app.services.invites import InviteService

_PW = "Password12345"


async def _issue_invite(session_factory) -> str:
    async with session_factory() as session:
        _, raw = await InviteService(session).create(note="t", expires_in_days=30)
    return raw


async def _register(client, code: str, org: str, email: str):
    return await client.post("/api/v1/auth/register", json={
        "invite_code": code, "organization_name": org,
        "admin_name": f"{org} Admin", "admin_email": email, "admin_password": _PW,
    })


async def _promote(session_factory, email: str) -> None:
    async with session_factory() as s:
        u = (await s.execute(select(User).where(User.email == email))).scalar_one()
        u.is_platform_admin = True
        await s.commit()


async def test_registration_starts_a_14_day_trial(client, session_factory):
    await _register(client, await _issue_invite(session_factory), "Trial Co", "a@trial.com")
    async with session_factory() as s:
        org = (await s.execute(select(Organization).where(Organization.name == "Trial Co"))).scalar_one()
    assert org.subscription_status is SubscriptionStatus.TRIALING
    assert org.trial_ends_at is not None
    days_left = (as_utc(org.trial_ends_at) - utcnow()).days
    assert 12 <= days_left <= 14


async def test_platform_console_requires_super_admin(client, session_factory):
    reg = await _register(client, await _issue_invite(session_factory), "Ops Co", "ops@ops.com")
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    # A normal org admin is NOT a platform admin.
    assert (await client.get("/api/v1/platform/organizations", headers=headers)).status_code == 403

    # A separate customer org that the operator should see.
    await _register(client, await _issue_invite(session_factory), "Customer Co", "c@cust.com")

    await _promote(session_factory, "ops@ops.com")
    listing = await client.get("/api/v1/platform/organizations", headers=headers)
    assert listing.status_code == 200
    names = {o["name"] for o in listing.json()}
    # Customers are listed; the operator's OWN org (it holds a platform admin) is not.
    assert "Customer Co" in names
    assert "Ops Co" not in names
    cust = next(o for o in listing.json() if o["name"] == "Customer Co")
    assert cust["user_count"] >= 1


async def test_trial_expiry_makes_org_read_only(client, session_factory):
    reg = await _register(client, await _issue_invite(session_factory), "Expire Co", "e@e.com")
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    # Trialing -> writes allowed.
    ok = await client.post("/api/v1/users", headers=headers,
                           json={"email": "u1@e.com", "full_name": "U1", "password": _PW, "role": "user"})
    assert ok.status_code in (200, 201), ok.text

    # Expire the trial.
    async with session_factory() as s:
        org = (await s.execute(select(Organization).where(Organization.name == "Expire Co"))).scalar_one()
        org.trial_ends_at = utcnow() - timedelta(days=1)
        await s.commit()

    # Writes now blocked (402), reads still fine.
    blocked = await client.post("/api/v1/users", headers=headers,
                                json={"email": "u2@e.com", "full_name": "U2", "password": _PW, "role": "user"})
    assert blocked.status_code == 402
    assert (await client.get("/api/v1/users", headers=headers)).status_code == 200


async def test_operator_can_extend_trial_to_reenable_writes(client, session_factory):
    reg = await _register(client, await _issue_invite(session_factory), "Extend Co", "x@x.com")
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    await _promote(session_factory, "x@x.com")

    # Expire, confirm read-only.
    async with session_factory() as s:
        org = (await s.execute(select(Organization).where(Organization.name == "Extend Co"))).scalar_one()
        org.trial_ends_at = utcnow() - timedelta(days=1)
        await s.commit()
        org_id = str(org.id)
    assert (await client.post("/api/v1/users", headers=headers,
            json={"email": "n@x.com", "full_name": "N", "password": _PW, "role": "user"})).status_code == 402

    # Operator extends the trial (platform routes are exempt from the gate).
    ext = await client.patch(f"/api/v1/platform/organizations/{org_id}", headers=headers,
                             json={"extend_trial_days": 14})
    assert ext.status_code == 200

    # Writes work again.
    assert (await client.post("/api/v1/users", headers=headers,
            json={"email": "n@x.com", "full_name": "N", "password": _PW, "role": "user"})).status_code in (200, 201)


async def test_operator_can_view_an_orgs_users_and_devices(client, session_factory):
    reg = await _register(client, await _issue_invite(session_factory), "Detail Co", "d@d.com")
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    await _promote(session_factory, "d@d.com")
    async with session_factory() as s:
        oid = str((await s.execute(select(Organization).where(Organization.name == "Detail Co"))).scalar_one().id)

    # Populate the org with a user and an enrolled device.
    await client.post("/api/v1/users", headers=headers,
                      json={"email": "member@d.com", "full_name": "M", "password": _PW, "role": "user"})
    tok = await client.post("/api/v1/devices/enrollment-tokens", headers=headers, json={"name": "f"})
    await client.post("/api/v1/agent/enroll", json={
        "enrollment_token": tok.json()["token"], "hostname": "D-PC",
        "machine_id": "d1", "os_version": "Windows 11", "agent_version": "0.1.0"})

    users = (await client.get(f"/api/v1/platform/organizations/{oid}/users", headers=headers)).json()
    assert any(u["email"] == "member@d.com" for u in users)
    devices = (await client.get(f"/api/v1/platform/organizations/{oid}/devices", headers=headers)).json()
    assert any(dv["hostname"] == "D-PC" for dv in devices)

    # A normal org admin (not platform admin) cannot use the platform detail routes.
    other = await _register(client, await _issue_invite(session_factory), "Other Co", "o@o.com")
    h2 = {"Authorization": f"Bearer {other.json()['access_token']}"}
    assert (await client.get(f"/api/v1/platform/organizations/{oid}/users", headers=h2)).status_code == 403


async def test_global_knowledge_reaches_every_org(client, session_factory):
    # Operator adds a global problem+solution.
    reg = await _register(client, await _issue_invite(session_factory), "KB Ops", "kb@ops.com")
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    await _promote(session_factory, "kb@ops.com")
    made = await client.post("/api/v1/platform/knowledge", headers=headers, json={
        "title": "Outlook stuck on loading profile",
        "content": "Start Outlook in safe mode: hold Ctrl while launching, then disable add-ins.",
    })
    assert made.status_code == 201, made.text

    listing = await client.get("/api/v1/platform/knowledge", headers=headers)
    assert any(a["title"].startswith("Outlook stuck") for a in listing.json())

    # A DIFFERENT org's assistant search finds the global article (proves it applies
    # to all orgs, even one that authored nothing itself).
    from app.services.ai.knowledge import KnowledgeBaseService
    from app.models import Organization
    from sqlalchemy import select as _select

    async with session_factory() as s:
        other = Organization(name="Some Other Co")
        s.add(other)
        await s.flush()
        found = await KnowledgeBaseService(s).search(org_id=other.id, query="outlook won't load my profile")
    assert any(a.title.startswith("Outlook stuck") for a in found)

    # Non-platform-admin can't manage global knowledge.
    other_reg = await _register(client, await _issue_invite(session_factory), "Plain Co", "plain@co.com")
    h2 = {"Authorization": f"Bearer {other_reg.json()['access_token']}"}
    assert (await client.get("/api/v1/platform/knowledge", headers=h2)).status_code == 403
    assert (await client.post("/api/v1/platform/knowledge", headers=h2,
            json={"title": "x", "content": "y"})).status_code == 403


async def test_operator_sees_org_remediation_and_assets(client, session_factory):
    reg = await _register(client, await _issue_invite(session_factory), "Support Co", "sup@co.com")
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    await _promote(session_factory, "sup@co.com")
    async with session_factory() as s:
        oid = str((await s.execute(select(Organization).where(Organization.name == "Support Co"))).scalar_one().id)

    # Create an asset in the org.
    await client.post("/api/v1/assets", headers=headers, json={"name": "Reception laptop", "category": "laptop"})

    # Platform detail endpoints respond (support visibility).
    assets = await client.get(f"/api/v1/platform/organizations/{oid}/assets", headers=headers)
    assert assets.status_code == 200
    assert any(a["name"] == "Reception laptop" for a in assets.json())

    remediation = await client.get(f"/api/v1/platform/organizations/{oid}/remediation", headers=headers)
    assert remediation.status_code == 200  # may be empty, but the endpoint works


async def test_operator_can_suspend_and_reactivate(client, session_factory):
    reg = await _register(client, await _issue_invite(session_factory), "Susp Co", "s@s.com")
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    await _promote(session_factory, "s@s.com")
    async with session_factory() as s:
        org_id = str((await s.execute(select(Organization).where(Organization.name == "Susp Co"))).scalar_one().id)

    # Suspend -> read-only.
    assert (await client.patch(f"/api/v1/platform/organizations/{org_id}", headers=headers,
            json={"subscription_status": "suspended"})).status_code == 200
    assert (await client.post("/api/v1/users", headers=headers,
            json={"email": "z@s.com", "full_name": "Z", "password": _PW, "role": "user"})).status_code == 402

    # Reactivate -> writable.
    assert (await client.patch(f"/api/v1/platform/organizations/{org_id}", headers=headers,
            json={"subscription_status": "active"})).status_code == 200
    assert (await client.post("/api/v1/users", headers=headers,
            json={"email": "z@s.com", "full_name": "Z", "password": _PW, "role": "user"})).status_code in (200, 201)
