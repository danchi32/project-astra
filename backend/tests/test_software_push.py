"""A2 + A4 — install catalog software on chosen devices/groups, per-device status."""
import pytest
from sqlalchemy import select

from app.models import RemediationTask
from app.services.ai.tools import _ACTION_IDS
from app.services.remediation.actions import ACTIONS, RemediationTier
from app.services.remediation.service import RemediationError, RemediationService


def test_install_is_approval_tier_elevated_and_withheld_from_ai():
    a = ACTIONS["install_package"]
    assert a.tier is RemediationTier.APPROVAL_REQUIRED
    assert a.execution_context == "system"
    assert a.operator_only is True
    assert "install_package" not in _ACTION_IDS


def test_only_catalog_ids_are_accepted():
    svc = RemediationService.__new__(RemediationService)
    assert svc._validate_params("install_package", {"package_id": "Google.Chrome"}) == {
        "package_id": "Google.Chrome"}
    for bad in ("Evil.Malware", "https://x/setup.exe", "", None):
        with pytest.raises(RemediationError):
            svc._validate_params("install_package", {"package_id": bad})


async def _enroll(client, admin_headers, host):
    key = (await client.get("/api/v1/devices/installer", headers=admin_headers)).json()["enrollment_key"]
    r = await client.post("/api/v1/agent/enroll", json={
        "enrollment_token": key, "hostname": host, "machine_id": host.lower(),
        "os_version": "Windows 11", "agent_version": "0.14.0"})
    return r.json()["device_id"]


async def test_catalog_is_listed_for_staff_only(client, admin_headers, user_headers):
    r = await client.get("/api/v1/software/catalog", headers=admin_headers)
    assert r.status_code == 200
    assert {"package_id": "Google.Chrome", "name": "Google Chrome", "publisher": "Google",
            "category": "Browser"} in r.json()
    assert (await client.get("/api/v1/software/catalog", headers=user_headers)).status_code == 403


async def test_push_to_group_minus_one_device(client, admin_headers, session_factory):
    a = await _enroll(client, admin_headers, "FIN-1")
    b = await _enroll(client, admin_headers, "FIN-2")
    c = await _enroll(client, admin_headers, "FIN-3")
    other = await _enroll(client, admin_headers, "HR-1")
    g = (await client.post("/api/v1/grouping/groups", headers=admin_headers,
                           json={"name": "Finance"})).json()
    put = await client.put(f"/api/v1/grouping/groups/{g['id']}/devices", headers=admin_headers,
                           json={"device_ids": [a, b, c]})
    assert put.status_code == 200, put.text

    r = await client.post("/api/v1/deployments/install", headers=admin_headers, json={
        "package_id": "Google.Chrome", "group_ids": [g["id"]], "device_ids": [other],
        "exclude_device_ids": [c], "reason": "Standard browser"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert (body["queued"], body["failed"], body["title"]) == (3, 0, "Install Google Chrome")

    async with session_factory() as s:
        tasks = (await s.execute(select(RemediationTask))).scalars().all()
    assert len(tasks) == 3 and all(t.action_id == "install_package" for t in tasks)
    assert all(t.status.value == "approved" for t in tasks)          # the pusher approved inline

    detail = (await client.get(f"/api/v1/deployments/{body['id']}", headers=admin_headers)).json()
    assert [d["hostname"] for d in detail["devices"]] == ["FIN-1", "FIN-2", "HR-1"]
    assert detail["status_counts"] == {"approved": 3}

    listed = (await client.get("/api/v1/deployments", headers=admin_headers)).json()
    assert listed[0]["id"] == body["id"] and listed[0]["status_counts"] == {"approved": 3}

    # Pushing the same thing again doesn't stack duplicates on devices still waiting.
    again = (await client.post("/api/v1/deployments/install", headers=admin_headers, json={
        "package_id": "Google.Chrome", "device_ids": [a], "reason": "again"})).json()
    assert (again["queued"], again["already_running"]) == (0, 1)


async def test_refusals(client, admin_headers, user_headers):
    a = await _enroll(client, admin_headers, "PC-1")
    bad = await client.post("/api/v1/deployments/install", headers=admin_headers, json={
        "package_id": "Evil.Malware", "device_ids": [a], "reason": "nope"})
    assert bad.status_code in (400, 422)
    empty = await client.post("/api/v1/deployments/install", headers=admin_headers, json={
        "package_id": "Google.Chrome", "device_ids": [a], "exclude_device_ids": [a], "reason": "x y"})
    assert empty.status_code in (400, 422)
    plain = await client.post("/api/v1/deployments/install", headers=user_headers, json={
        "package_id": "Google.Chrome", "device_ids": [a], "reason": "x y"})
    assert plain.status_code == 403
