"""Organization settings, permission matrix, profile & password — including the
four places org policy actually changes backend behavior."""
from app.models import UserRole
from tests.conftest import USER_PASSWORD, _create_user, auth_headers


async def _enroll(client, admin_headers, hostname="SET-PC", machine="set-machine"):
    tok = await client.post(
        "/api/v1/devices/enrollment-tokens", json={"name": "set"}, headers=admin_headers
    )
    enroll = await client.post(
        "/api/v1/agent/enroll",
        json={
            "enrollment_token": tok.json()["token"],
            "hostname": hostname,
            "machine_id": machine,
            "os_version": "Windows 11",
            "agent_version": "0.1.0",
        },
    )
    return enroll.json()


# ── Organization settings CRUD + RBAC ──────────────────────────────────────


async def test_get_settings_returns_defaults(client, admin_headers):
    resp = await client.get("/api/v1/settings/organization", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["org_name"] == "Acme Corp"
    assert body["auto_approve_automatic"] is True
    assert body["require_admin_for_approval_tier"] is False
    assert body["min_password_length"] == 8
    assert body["enrollment_token_default_days"] == 7


async def test_non_admin_cannot_read_or_write_settings(client, user_headers):
    assert (await client.get("/api/v1/settings/organization", headers=user_headers)).status_code == 403
    resp = await client.patch(
        "/api/v1/settings/organization", json={"org_name": "Hacked"}, headers=user_headers
    )
    assert resp.status_code == 403


async def test_update_settings_persists_and_audits(client, admin_headers):
    resp = await client.patch(
        "/api/v1/settings/organization",
        json={
            "org_name": "Acme Global",
            "auto_approve_automatic": False,
            "min_password_length": 16,
            "enrollment_token_default_days": 30,
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["org_name"] == "Acme Global"
    assert body["auto_approve_automatic"] is False
    assert body["min_password_length"] == 16
    assert body["enrollment_token_default_days"] == 30

    # persisted
    again = await client.get("/api/v1/settings/organization", headers=admin_headers)
    assert again.json()["org_name"] == "Acme Global"

    logs = await client.get("/api/v1/audit-logs", headers=admin_headers)
    assert "settings.update" in [e["action"] for e in logs.json()]


async def test_settings_require_auth(client):
    assert (await client.get("/api/v1/settings/organization")).status_code == 401


# ── Permission matrix ──────────────────────────────────────────────────────


async def test_permission_matrix_is_readable_by_any_user(client, user_headers):
    resp = await client.get("/api/v1/settings/permissions", headers=user_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    roles = {r["role"]: r for r in body["roles"]}
    # Admin can do everything; user is read-only.
    assert all(roles["admin"]["capabilities"].values())
    assert roles["user"]["capabilities"]["view_platform"] is True
    assert roles["user"]["capabilities"]["manage_users"] is False
    # By default a technician may approve standard remediations.
    assert roles["technician"]["capabilities"]["approve_standard"] is True


async def test_permission_matrix_reflects_admin_only_approval_policy(client, admin_headers):
    await client.patch(
        "/api/v1/settings/organization",
        json={"require_admin_for_approval_tier": True},
        headers=admin_headers,
    )
    resp = await client.get("/api/v1/settings/permissions", headers=admin_headers)
    roles = {r["role"]: r for r in resp.json()["roles"]}
    assert roles["technician"]["capabilities"]["approve_standard"] is False


# ── Behavior wiring: automation kill-switch ────────────────────────────────


async def test_auto_approve_kill_switch_forces_pending(client, admin_headers):
    enrolled = await _enroll(client, admin_headers)
    # Baseline: an automatic action is auto-approved.
    baseline = await client.post(
        "/api/v1/remediations",
        json={"device_id": enrolled["device_id"], "action_id": "flush_dns", "reason": "dns"},
        headers=admin_headers,
    )
    assert baseline.json()["status"] == "approved"

    # Turn the kill-switch off — now even automatic actions wait for approval.
    await client.patch(
        "/api/v1/settings/organization",
        json={"auto_approve_automatic": False},
        headers=admin_headers,
    )
    gated = await client.post(
        "/api/v1/remediations",
        json={"device_id": enrolled["device_id"], "action_id": "flush_dns", "reason": "dns again"},
        headers=admin_headers,
    )
    assert gated.json()["status"] == "pending_approval"


# ── Behavior wiring: admin-only approval policy ────────────────────────────


async def test_require_admin_for_approval_tier(client, admin_headers, session_factory, org):
    enrolled = await _enroll(client, admin_headers)
    tech = await _create_user(
        session_factory, org.id, "tech@acme.com", USER_PASSWORD, UserRole.TECHNICIAN
    )
    tech_headers = await auth_headers(client, tech.email, USER_PASSWORD)

    # Tighten policy: approval-required tier now needs an admin.
    await client.patch(
        "/api/v1/settings/organization",
        json={"require_admin_for_approval_tier": True},
        headers=admin_headers,
    )
    created = await client.post(
        "/api/v1/remediations",
        json={"device_id": enrolled["device_id"], "action_id": "office_repair", "reason": "x"},
        headers=admin_headers,
    )
    task_id = created.json()["id"]

    # Technician is blocked...
    denied = await client.post(f"/api/v1/remediations/{task_id}/approve", headers=tech_headers)
    assert denied.status_code >= 400
    # ...admin still succeeds.
    ok = await client.post(f"/api/v1/remediations/{task_id}/approve", headers=admin_headers)
    assert ok.status_code == 200
    assert ok.json()["status"] == "approved"


# ── Behavior wiring: password policy ───────────────────────────────────────


async def test_min_password_length_enforced_on_user_create(client, admin_headers):
    await client.patch(
        "/api/v1/settings/organization",
        json={"min_password_length": 16},
        headers=admin_headers,
    )
    # 12 chars satisfies the schema floor (8) but not the org's 16-char policy.
    resp = await client.post(
        "/api/v1/users",
        json={"email": "new@acme.com", "full_name": "New", "password": "Passw0rd!123", "role": "user"},
        headers=admin_headers,
    )
    assert resp.status_code == 400
    assert "16 characters" in resp.json()["detail"]


# ── Profile & password ─────────────────────────────────────────────────────


async def test_update_own_profile(client, admin_headers):
    resp = await client.patch(
        "/api/v1/auth/me", json={"full_name": "Renamed Admin"}, headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Renamed Admin"


async def test_change_password_success_and_revokes_sessions(client, admin_user):
    from tests.conftest import ADMIN_PASSWORD

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": ADMIN_PASSWORD},
    )
    access = login.json()["access_token"]
    refresh = login.json()["refresh_token"]

    resp = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": ADMIN_PASSWORD, "new_password": "BrandNewPass!99"},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert resp.status_code == 204, resp.text

    # Old refresh token is now revoked.
    reused = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert reused.status_code == 401
    # New password works for a fresh login.
    relogin = await client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "BrandNewPass!99"},
    )
    assert relogin.status_code == 200


async def test_change_password_rejects_wrong_current(client, admin_headers):
    resp = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "WrongPassword!1", "new_password": "AnotherNewPass!9"},
        headers=admin_headers,
    )
    assert resp.status_code == 400


async def test_change_password_enforces_org_minimum(client, admin_headers, admin_user):
    from tests.conftest import ADMIN_PASSWORD

    await client.patch(
        "/api/v1/settings/organization",
        json={"min_password_length": 20},
        headers=admin_headers,
    )
    # 15 chars — above the schema floor (8) but below the org's 20.
    resp = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": ADMIN_PASSWORD, "new_password": "FifteenChars!12"},
        headers=admin_headers,
    )
    assert resp.status_code == 400
    assert "20 characters" in resp.json()["detail"]
