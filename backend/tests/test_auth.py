from sqlalchemy import select

from app.models import AuditLog
from tests.conftest import ADMIN_PASSWORD, login


async def test_login_returns_token_pair(client, admin_user):
    tokens = await login(client, admin_user.email, ADMIN_PASSWORD)
    assert tokens["access_token"]
    assert tokens["refresh_token"]
    assert tokens["token_type"] == "bearer"


async def test_login_wrong_password_rejected(client, admin_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "definitely-wrong-password"},
    )
    assert response.status_code == 401


async def test_login_unknown_email_rejected(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@nowhere.com", "password": "irrelevant-password"},
    )
    assert response.status_code == 401


async def test_login_writes_audit_entry(client, admin_user, session_factory):
    await login(client, admin_user.email, ADMIN_PASSWORD)
    async with session_factory() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.action == "auth.login"))
        entries = result.scalars().all()
    assert len(entries) == 1
    assert entries[0].actor_id == admin_user.id


async def test_me_returns_current_user(client, admin_headers, admin_user):
    response = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == admin_user.email
    assert body["role"] == "admin"
    assert "hashed_password" not in body


async def test_me_without_token_rejected(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_with_garbage_token_rejected(client):
    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


async def test_refresh_rotates_and_invalidates_old_token(client, admin_user):
    tokens = await login(client, admin_user.email, ADMIN_PASSWORD)
    old_refresh = tokens["refresh_token"]

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert response.status_code == 200
    new_tokens = response.json()
    assert new_tokens["refresh_token"] != old_refresh

    # The consumed refresh token must be rejected on reuse.
    replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert replay.status_code == 401


async def test_logout_revokes_refresh_token(client, admin_user):
    tokens = await login(client, admin_user.email, ADMIN_PASSWORD)
    response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}
    )
    assert response.status_code == 204

    reuse = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert reuse.status_code == 401
