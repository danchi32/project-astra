from sqlalchemy import select

from app.models import AuditLog
from tests.conftest import USER_PASSWORD, login

NEW_USER = {
    "email": "tech@acme.com",
    "full_name": "Terry Tech",
    "password": "TechPassw0rd!234",
    "role": "technician",
}


async def test_admin_creates_user(client, admin_headers):
    response = await client.post("/api/v1/users", json=NEW_USER, headers=admin_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == "tech@acme.com"
    assert body["role"] == "technician"
    assert "password" not in body and "hashed_password" not in body


async def test_user_create_writes_audit_entry(client, admin_headers, admin_user, session_factory):
    await client.post("/api/v1/users", json=NEW_USER, headers=admin_headers)
    async with session_factory() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.action == "user.create"))
        entries = result.scalars().all()
    assert len(entries) == 1
    assert entries[0].actor_id == admin_user.id
    assert entries[0].detail["email"] == "tech@acme.com"


async def test_regular_user_cannot_create_user(client, user_headers):
    response = await client.post("/api/v1/users", json=NEW_USER, headers=user_headers)
    assert response.status_code == 403


async def test_regular_user_cannot_list_users(client, user_headers):
    response = await client.get("/api/v1/users", headers=user_headers)
    assert response.status_code == 403


async def test_list_users_requires_auth(client):
    response = await client.get("/api/v1/users")
    assert response.status_code == 401


async def test_list_users_is_org_scoped(client, admin_headers, regular_user, other_org_user):
    response = await client.get("/api/v1/users", headers=admin_headers)
    assert response.status_code == 200
    emails = {u["email"] for u in response.json()}
    assert regular_user.email in emails
    assert other_org_user.email not in emails


async def test_get_user_from_other_org_is_404(client, admin_headers, other_org_user):
    response = await client.get(f"/api/v1/users/{other_org_user.id}", headers=admin_headers)
    assert response.status_code == 404


async def test_duplicate_email_conflict(client, admin_headers, regular_user):
    duplicate = {**NEW_USER, "email": regular_user.email}
    response = await client.post("/api/v1/users", json=duplicate, headers=admin_headers)
    assert response.status_code == 409


async def test_short_password_rejected(client, admin_headers):
    weak = {**NEW_USER, "password": "short"}
    response = await client.post("/api/v1/users", json=weak, headers=admin_headers)
    assert response.status_code == 422


async def test_admin_updates_role(client, admin_headers, regular_user):
    response = await client.patch(
        f"/api/v1/users/{regular_user.id}", json={"role": "technician"}, headers=admin_headers
    )
    assert response.status_code == 200
    assert response.json()["role"] == "technician"


async def test_deactivation_revokes_sessions(client, admin_headers, regular_user):
    # User logs in, then an admin deactivates them.
    tokens = await login(client, regular_user.email, USER_PASSWORD)
    response = await client.patch(
        f"/api/v1/users/{regular_user.id}", json={"is_active": False}, headers=admin_headers
    )
    assert response.status_code == 200

    # Their access token and refresh token must both stop working.
    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.status_code == 401
    refresh = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh.status_code == 401


async def test_admin_cannot_delete_self(client, admin_headers, admin_user):
    response = await client.delete(f"/api/v1/users/{admin_user.id}", headers=admin_headers)
    assert response.status_code == 409


async def test_admin_deletes_user(client, admin_headers, regular_user):
    response = await client.delete(f"/api/v1/users/{regular_user.id}", headers=admin_headers)
    assert response.status_code == 204
    gone = await client.get(f"/api/v1/users/{regular_user.id}", headers=admin_headers)
    assert gone.status_code == 404
