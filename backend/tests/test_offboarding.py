"""Secure offboarding: disabling/enabling a local account is admin-only, elevated (system
context), and its username is strictly validated."""
import pytest

from app.models import UserRole
from app.services.remediation.actions import get_action, RemediationTier
from app.services.remediation.service import _validate_username, RemediationError
from tests.conftest import USER_PASSWORD, _create_user, auth_headers
from tests.test_remediation import _enroll, _device_id


def test_offboarding_actions_are_admin_only_and_system():
    for aid in ("disable_local_account", "enable_local_account"):
        a = get_action(aid)
        assert a is not None
        assert a.tier is RemediationTier.ADMIN_ONLY       # highest tier
        assert a.execution_context == "system"            # elevated service runs it
        assert "username" in a.params


def test_username_validation():
    assert _validate_username("jsmith") == "jsmith"
    assert _validate_username("  John Doe  ") == "John Doe"
    assert _validate_username("a.b_c-1") == "a.b_c-1"
    # Devices report "DOMAIN\\user" (DOMAIN = machine name for a local account) — strip it.
    assert _validate_username("LSI-1322\\Rahul") == "Rahul"
    assert _validate_username("ACME\\John Doe") == "John Doe"
    for bad in ("", "a/b", "x;drop", 'q"uote', "user@dom", "a" * 70, "n[ame]", "dom\\"):
        with pytest.raises(RemediationError):
            _validate_username(bad)


async def test_disable_account_admin_only_and_routes_to_system(client, admin_headers):
    enroll = await _enroll(client, admin_headers)
    device_headers = {"Authorization": f"Bearer {enroll['device_token']}"}
    device_id = await _device_id(client, admin_headers)

    create = await client.post("/api/v1/remediations", headers=admin_headers, json={
        "device_id": device_id, "action_id": "disable_local_account",
        "reason": "employee offboarded", "params": {"username": "jdoe"}})
    assert create.status_code == 201, create.text
    task = create.json()
    assert task["status"] == "pending_approval"     # admin_only never auto-approves
    assert task["tier"] == "admin_only"

    approve = await client.post(f"/api/v1/remediations/{task['id']}/approve", headers=admin_headers)
    assert approve.status_code == 200

    # The user-session Tray must never receive this elevated action.
    uc = await client.get("/api/v1/agent/tasks", headers=device_headers)
    assert task["id"] not in [t["id"] for t in uc.json()]
    # The elevated Service claims it, carrying the validated username.
    sc = await client.get("/api/v1/agent/tasks?context=system", headers=device_headers)
    rows = sc.json()
    assert [r["action_id"] for r in rows] == ["disable_local_account"]
    assert rows[0]["params"]["username"] == "jdoe"


async def test_technician_cannot_approve_offboarding(client, admin_headers, session_factory, org):
    await _enroll(client, admin_headers)
    device_id = await _device_id(client, admin_headers)
    tech = await _create_user(session_factory, org.id, "offb-tech@acme.com", USER_PASSWORD, UserRole.TECHNICIAN)
    tech_headers = await auth_headers(client, tech.email, USER_PASSWORD)

    create = await client.post("/api/v1/remediations", headers=admin_headers, json={
        "device_id": device_id, "action_id": "disable_local_account",
        "reason": "x", "params": {"username": "jdoe"}})
    tid = create.json()["id"]
    denied = await client.post(f"/api/v1/remediations/{tid}/approve", headers=tech_headers)
    assert denied.status_code >= 400     # admin_only tier — technician may not approve
