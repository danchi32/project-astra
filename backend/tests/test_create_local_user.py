"""A1 — create a local Windows account: admin-only, elevated, never the AI's to propose."""
import pytest

from app.services.ai.tools import _ACTION_IDS
from app.services.remediation.actions import ACTIONS, RemediationTier
from app.services.remediation.service import RemediationError, RemediationService


def test_registry_entry_is_admin_only_elevated_and_withheld_from_ai():
    a = ACTIONS["create_local_user"]
    assert a.tier is RemediationTier.ADMIN_ONLY
    assert a.execution_context == "system"
    assert a.operator_only is True
    assert "create_local_user" not in _ACTION_IDS


@pytest.mark.parametrize("params, expected", [
    ({"username": "asha", "full_name": "Asha Sharma", "make_admin": True},
     {"username": "asha", "full_name": "Asha Sharma", "make_admin": "true"}),
    ({"username": "front.desk", "full_name": ""},
     {"username": "front.desk", "full_name": "", "make_admin": "false"}),
    ({"username": "asha", "full_name": "A", "make_admin": "false"},
     {"username": "asha", "full_name": "A", "make_admin": "false"}),
])
def test_params_normalise_for_the_agent(session_factory, params, expected):
    # The agent reads params as string->string; a JSON boolean would not deserialize there.
    svc = RemediationService.__new__(RemediationService)
    assert svc._validate_params("create_local_user", dict(params)) == expected


@pytest.mark.parametrize("params", [
    {"username": "ACME\asha", "full_name": "x"},                 # never a domain account
    {"username": "a-name-longer-than-20c", "full_name": "x"},     # SAM limit
    {"username": "bad;name", "full_name": "x"},
    {"username": "asha", "full_name": "x" * 101},
    {"username": "asha", "full_name": "<script>"},
    {"username": "asha", "full_name": "x", "make_admin": "yes"},
    {"username": "asha", "full_name": "x", "password": "Hunter2!"},  # portal never sends one
])
def test_bad_params_are_refused(params):
    svc = RemediationService.__new__(RemediationService)
    with pytest.raises(RemediationError):
        svc._validate_params("create_local_user", dict(params))


async def _device(client, admin_headers):
    key = (await client.get("/api/v1/devices/installer", headers=admin_headers)).json()["enrollment_key"]
    r = await client.post("/api/v1/agent/enroll", json={
        "enrollment_token": key, "hostname": "NEWHIRE-PC", "machine_id": "nh-1",
        "os_version": "Windows 11", "agent_version": "0.14.0"})
    return r.json()["device_id"]


async def test_admin_can_queue_it_a_plain_user_cannot(client, admin_headers, user_headers):
    device_id = await _device(client, admin_headers)
    body = {"device_id": device_id, "action_id": "create_local_user",
            "params": {"username": "asha", "full_name": "Asha Sharma", "make_admin": False},
            "reason": "New joiner", "approve": True}
    ok = await client.post("/api/v1/remediations", json=body, headers=admin_headers)
    assert ok.status_code in (200, 201), ok.text
    assert ok.json()["params"]["make_admin"] == "false"
    denied = await client.post("/api/v1/remediations", json=body, headers=user_headers)
    assert denied.status_code in (403, 409, 422)


# ── Users tab: the account list and the admin toggle ────────────────────────

def test_admin_toggle_is_admin_only_elevated_and_withheld_from_ai():
    a = ACTIONS["set_local_admin"]
    assert a.tier is RemediationTier.ADMIN_ONLY
    assert a.execution_context == "system"
    assert a.operator_only is True
    assert "set_local_admin" not in _ACTION_IDS


def test_admin_toggle_params():
    svc = RemediationService.__new__(RemediationService)
    assert svc._validate_params("set_local_admin", {"username": "asha", "make_admin": False}) == {
        "username": "asha", "make_admin": "false"}
    with pytest.raises(RemediationError):
        svc._validate_params("set_local_admin", {"username": "bad;name", "make_admin": True})


ACCOUNTS = [
    {"name": "Administrator", "enabled": False, "is_admin": True, "built_in": True},
    {"name": "Danish", "full_name": "Danish", "enabled": True, "is_admin": True},
    {"name": "asha", "full_name": "Asha Sharma", "enabled": True, "is_admin": False},
]
PUSH = {"collected_at": "2026-11-11T10:00:00Z", "cpu_percent": 5.0, "ram_total_mb": 8192,
        "ram_used_mb": 2048, "disks": [{"drive": "C:", "total_gb": 100.0, "used_gb": 20.0, "free_gb": 80.0}]}


async def test_accounts_are_stored_listed_and_kept_between_inventories(client, admin_headers, user_headers):
    key = (await client.get("/api/v1/devices/installer", headers=admin_headers)).json()["enrollment_key"]
    enrolled = (await client.post("/api/v1/agent/enroll", json={
        "enrollment_token": key, "hostname": "USERS-PC", "machine_id": "users-1",
        "os_version": "Windows 11", "agent_version": "0.14.0"})).json()
    dev = {"Authorization": f"Bearer {enrolled['device_token']}"}

    assert (await client.post("/api/v1/agent/telemetry", json=dict(PUSH, local_accounts=ACCOUNTS),
                              headers=dev)).status_code in (200, 201, 204)
    # A push between inventories carries no list and must not wipe it.
    await client.post("/api/v1/agent/telemetry", json=PUSH, headers=dev)

    r = await client.get(f"/api/v1/devices/{enrolled['device_id']}/local-accounts", headers=admin_headers)
    assert r.status_code == 200, r.text
    rows = r.json()
    # Real people first, built-ins last.
    assert [a["name"] for a in rows] == ["Danish", "asha", "Administrator"]
    assert next(a for a in rows if a["name"] == "asha")["is_admin"] is False

    # Staff only — a plain portal user doesn't get the machine's account list.
    denied = await client.get(f"/api/v1/devices/{enrolled['device_id']}/local-accounts", headers=user_headers)
    assert denied.status_code == 403
