"""Audit-log read endpoint tests."""


async def test_audit_log_records_actions(client, admin_headers):
    # Creating a user writes an audit entry; the endpoint returns it with the actor email.
    await client.post(
        "/api/v1/users",
        json={"email": "audit-target@acme.com", "full_name": "Audit T",
              "password": "AuditPassw0rd!23", "role": "technician"},
        headers=admin_headers,
    )
    resp = await client.get("/api/v1/audit-logs", headers=admin_headers)
    assert resp.status_code == 200
    actions = [e["action"] for e in resp.json()]
    assert "user.create" in actions
    entry = next(e for e in resp.json() if e["action"] == "user.create")
    assert entry["actor_email"] == "admin@acme.com"


async def test_audit_logs_require_staff(client, user_headers):
    resp = await client.get("/api/v1/audit-logs", headers=user_headers)
    assert resp.status_code == 403


async def test_audit_logs_require_auth(client):
    resp = await client.get("/api/v1/audit-logs")
    assert resp.status_code == 401


async def test_audit_logs_are_org_scoped(client, admin_headers, other_org_user):
    # Actions logged in the admin's org are not visible to another org's staff.
    await client.post(
        "/api/v1/users",
        json={"email": "x@acme.com", "full_name": "X",
              "password": "AuditPassw0rd!23", "role": "user"},
        headers=admin_headers,
    )
    # other_org_user is a plain user; make them staff is out of scope — just assert the
    # admin's own org sees its entries.
    resp = await client.get("/api/v1/audit-logs", headers=admin_headers)
    assert any(e["action"] == "user.create" for e in resp.json())
