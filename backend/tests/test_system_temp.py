"""System-context remediation: the elevated `clear_system_temp` cleanup, and the claim
routing that keeps user-session (Tray) and system (elevated Service) tasks separate so the
two agent processes never take each other's work."""
import json

import pytest

from app.services.ai.provider import StubProvider
from app.services.remediation.actions import get_action, RemediationTier
from tests.test_remediation import _enroll, _device_id


def test_slow_complaint_proposes_both_user_and_system_cleanup():
    # After gathering telemetry for a vague "it's slow" complaint, the built-in engine
    # should clean BOTH the user temp and the elevated machine-wide temp.
    telemetry = json.dumps({"cpu_percent": 90, "ram_percent": 80, "disks": []})
    resp = StubProvider()._follow_up_after_evidence([telemetry], "my whole system is really slow")
    assert resp is not None
    proposed = [
        c.input["action_id"] for c in resp.tool_calls if c.name == "propose_remediation"
    ]
    assert "clear_temp" in proposed
    assert "clear_system_temp" in proposed
    # Tool-call ids must be unique so both are dispatched.
    assert len({c.id for c in resp.tool_calls}) == len(resp.tool_calls)


def test_clear_system_temp_is_an_automatic_system_action():
    action = get_action("clear_system_temp")
    assert action is not None
    assert action.tier is RemediationTier.AUTOMATIC       # safe, self-rebuilding cleanup
    assert action.execution_context == "system"           # runs in the elevated service


def test_clear_temp_stays_user_context():
    action = get_action("clear_temp")
    assert action is not None
    assert action.execution_context == "user"


async def _make_task(client, admin_headers, device_id, action_id):
    resp = await client.post(
        "/api/v1/remediations",
        json={"device_id": device_id, "action_id": action_id, "reason": "device is slow"},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "approved"  # automatic → pre-approved
    return resp.json()["id"]


async def test_system_task_only_claimed_by_system_context(client, admin_headers):
    enroll = await _enroll(client, admin_headers)
    device_headers = {"Authorization": f"Bearer {enroll['device_token']}"}
    device_id = await _device_id(client, admin_headers)

    sys_task = await _make_task(client, admin_headers, device_id, "clear_system_temp")
    user_task = await _make_task(client, admin_headers, device_id, "clear_temp")

    # The Tray (default/user context) claims ONLY the user task — never the elevated one.
    user_claim = await client.get("/api/v1/agent/tasks", headers=device_headers)
    ids = [t["id"] for t in user_claim.json()]
    assert user_task in ids
    assert sys_task not in ids

    # The elevated Service claims the system task with ?context=system.
    sys_claim = await client.get("/api/v1/agent/tasks?context=system", headers=device_headers)
    sys_ids = [t["id"] for t in sys_claim.json()]
    assert sys_ids == [sys_task]

    # Once dispatched, a second system claim returns nothing.
    again = await client.get("/api/v1/agent/tasks?context=system", headers=device_headers)
    assert again.json() == []


def test_windows_update_install_is_system_context_approval_tier():
    action = get_action("windows_update_install")
    assert action is not None
    assert action.execution_context == "system"                 # elevated service runs it
    assert action.tier is RemediationTier.APPROVAL_REQUIRED      # gated (reboot risk)
    assert "kb_article_id" in action.params                      # can target one KB


def test_kb_article_id_validation():
    from app.services.remediation.service import _validate_kb_article_id, RemediationError
    assert _validate_kb_article_id("KB5034123") == "KB5034123"
    assert _validate_kb_article_id("5034123") == "KB5034123"    # bare digits get the KB prefix
    assert _validate_kb_article_id("kb5034123") == "KB5034123"  # case-normalized
    for bad in ("not-a-kb", "KB12", "KB; rm -rf", "KB123456789"):
        with pytest.raises(RemediationError):
            _validate_kb_article_id(bad)


async def test_push_windows_update_approval_then_routes_to_system(client, admin_headers):
    enroll = await _enroll(client, admin_headers)
    device_headers = {"Authorization": f"Bearer {enroll['device_token']}"}
    device_id = await _device_id(client, admin_headers)

    # Admin pushes a specific KB -> an approval-required task, pending until approved.
    create = await client.post("/api/v1/remediations", headers=admin_headers, json={
        "device_id": device_id, "action_id": "windows_update_install",
        "reason": "push from telemetry", "params": {"kb_article_id": "kb5034123"}})
    assert create.status_code == 201, create.text
    task = create.json()
    assert task["status"] == "pending_approval"
    assert task["tier"] == "approval_required"

    # Approve it (the admin's click does this in the portal).
    approve = await client.post(f"/api/v1/remediations/{task['id']}/approve", headers=admin_headers)
    assert approve.status_code == 200

    # The user-session Tray must NOT get it — it's a system (elevated) action.
    user_claim = await client.get("/api/v1/agent/tasks", headers=device_headers)
    assert task["id"] not in [t["id"] for t in user_claim.json()]

    # The elevated Service claims it, with the normalized KB param.
    sys_claim = await client.get("/api/v1/agent/tasks?context=system", headers=device_headers)
    rows = sys_claim.json()
    assert [r["action_id"] for r in rows] == ["windows_update_install"]
    assert rows[0]["params"]["kb_article_id"] == "KB5034123"


async def test_push_windows_update_rejects_bad_kb(client, admin_headers):
    await _enroll(client, admin_headers)
    device_id = await _device_id(client, admin_headers)
    r = await client.post("/api/v1/remediations", headers=admin_headers, json={
        "device_id": device_id, "action_id": "windows_update_install",
        "reason": "x", "params": {"kb_article_id": "; drop table"}})
    assert r.status_code == 400
    assert "kb" in r.text.lower()


async def test_unknown_context_falls_back_to_user(client, admin_headers):
    enroll = await _enroll(client, admin_headers)
    device_headers = {"Authorization": f"Bearer {enroll['device_token']}"}
    device_id = await _device_id(client, admin_headers)

    user_task = await _make_task(client, admin_headers, device_id, "flush_dns")
    await _make_task(client, admin_headers, device_id, "clear_system_temp")

    # A garbage context must not leak the elevated task — it's treated as "user".
    claim = await client.get("/api/v1/agent/tasks?context=bogus", headers=device_headers)
    ids = [t["id"] for t in claim.json()]
    assert ids == [user_task]
