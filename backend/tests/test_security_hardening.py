"""Security Phase 1: refresh-token reuse detection, security headers, security.txt."""
from tests.conftest import ADMIN_PASSWORD


async def test_refresh_token_reuse_revokes_the_family(client, admin_user):
    login = await client.post(
        "/api/v1/auth/login", json={"email": admin_user.email, "password": ADMIN_PASSWORD}
    )
    r1 = login.json()["refresh_token"]

    # Legitimate rotation: r1 is spent, r2 issued (same family).
    rot = await client.post("/api/v1/auth/refresh", json={"refresh_token": r1})
    assert rot.status_code == 200
    r2 = rot.json()["refresh_token"]

    # Replaying the spent r1 is treated as theft → 401 and the whole family is revoked.
    replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": r1})
    assert replay.status_code == 401

    # ...so even the otherwise-valid r2 no longer works — everyone must log in again.
    after = await client.post("/api/v1/auth/refresh", json={"refresh_token": r2})
    assert after.status_code == 401


async def test_security_headers_present(client):
    r = await client.get("/health")
    assert r.headers.get("strict-transport-security", "").startswith("max-age=")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"


async def test_security_txt_served(client):
    r = await client.get("/.well-known/security.txt")
    assert r.status_code == 200
    assert "Contact:" in r.text
    assert "Expires:" in r.text
