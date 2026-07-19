"""The operator console's cross-org read endpoints: billing, reports, audit — and
the view_as flag surfaced by /auth/me."""
from sqlalchemy import select

from app.models import User
from app.services.invites import InviteService

_PW = "Password12345"


async def _issue_invite(session_factory) -> str:
    async with session_factory() as session:
        _, raw = await InviteService(session).create(note="t", expires_in_days=30)
    return raw


async def _register_org(client, session_factory, org, email):
    return await client.post("/api/v1/auth/register", json={
        "invite_code": await _issue_invite(session_factory), "organization_name": org,
        "admin_name": "Admin", "admin_email": email, "admin_password": _PW,
    })


async def _operator(client, session_factory, org="Console Co", email="op@console.com"):
    """Register an org, promote its admin to platform admin, return auth headers."""
    reg = await _register_org(client, session_factory, org, email)
    async with session_factory() as s:
        u = (await s.execute(select(User).where(User.email == email))).scalar_one()
        u.is_platform_admin = True
        await s.commit()
    return {"Authorization": f"Bearer {reg.json()['access_token']}"}


async def test_billing_rollup_excludes_operator_own_org(client, session_factory):
    headers = await _operator(client, session_factory)
    await _register_org(client, session_factory, "Cust Co", "a@cust.com")

    response = await client.get("/api/v1/platform/billing", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    # A trialing customer, no per-seat price configured in tests → revenue is None.
    assert body["trialing"] >= 1
    assert body["active_subscriptions"] == 0
    assert body["mrr_cents"] is None and body["arr_cents"] is None
    names = {r["name"] for r in body["rows"]}
    assert "Cust Co" in names
    assert "Console Co" not in names  # the operator's own workspace is not a customer
    row = next(r for r in body["rows"] if r["name"] == "Cust Co")
    assert row["subscription_status"] == "trialing"
    assert row["license_count"] == 0


async def test_reports_rollup(client, session_factory):
    headers = await _operator(client, session_factory, org="Rep Co", email="op@rep.com")
    await _register_org(client, session_factory, "Rep Cust Co", "a@repcust.com")

    response = await client.get("/api/v1/platform/reports", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["signups_by_month"]) == 12
    # This month's customer signup is counted in the last bucket (operator org excluded).
    assert body["signups_by_month"][-1]["count"] >= 1
    assert body["remediation_total_30d"] == 0
    assert body["remediation_success_rate"] is None
    assert body["total_devices"] == 0


async def test_audit_feed_records_operator_actions(client, session_factory):
    headers = await _operator(client, session_factory, org="Aud Co", email="op@aud.com")
    await _register_org(client, session_factory, "Aud Cust", "a@audcust.com")
    # Do an audited platform action: mint a view-as token for a customer org.
    orgs = (await client.get("/api/v1/platform/organizations", headers=headers)).json()
    org_id = next(o["id"] for o in orgs if o["name"] == "Aud Cust")
    assert (await client.post(
        f"/api/v1/platform/organizations/{org_id}/view-token", headers=headers
    )).status_code == 200

    response = await client.get("/api/v1/platform/audit", headers=headers)
    assert response.status_code == 200, response.text
    feed = response.json()
    entry = next(e for e in feed if e["action"] == "platform.view_as")
    assert entry["org_name"] == "Aud Cust"
    assert entry["actor_email"] == "op@aud.com"


async def test_console_endpoints_require_platform_admin(client, session_factory):
    reg = await client.post("/api/v1/auth/register", json={
        "invite_code": await _issue_invite(session_factory), "organization_name": "Plain Co",
        "admin_name": "P", "admin_email": "p@plain.com", "admin_password": _PW,
    })
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    for path in ("/api/v1/platform/billing", "/api/v1/platform/reports", "/api/v1/platform/audit"):
        assert (await client.get(path, headers=headers)).status_code == 403


async def test_me_reports_view_as_mode(client, session_factory):
    headers = await _operator(client, session_factory, org="Me Co", email="op@me.com")
    await _register_org(client, session_factory, "Me Cust", "a@mecust.com")
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    assert me["view_as"] is False

    orgs = (await client.get("/api/v1/platform/organizations", headers=headers)).json()
    org_id = next(o["id"] for o in orgs if o["name"] == "Me Cust")
    token = (await client.post(
        f"/api/v1/platform/organizations/{org_id}/view-token", headers=headers
    )).json()["access_token"]
    viewed = (await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )).json()
    assert viewed["view_as"] is True
    assert viewed["org_id"] == org_id
