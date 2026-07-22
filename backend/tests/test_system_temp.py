"""System-context remediation: the elevated `clear_system_temp` cleanup, and the claim
routing that keeps user-session (Tray) and system (elevated Service) tasks separate so the
two agent processes never take each other's work."""
import json

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
