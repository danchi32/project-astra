"""Phase 1 security review (1f) — one test per backend finding that was fixed."""
import json
import re
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select

from app.core.security import hash_opaque_token
from app.models import (
    AuditLog,
    Device,
    Organization,
    RemediationSource,
    RemediationStatus,
    RemediationTask,
    User,
    UserRole,
)
from app.models.base import utcnow
from app.services.ai.tools import dispatch_tool
from app.services.software_catalog import CATALOG
from tests.conftest import ADMIN_PASSWORD, _create_user, auth_headers

AGENT = Path(__file__).resolve().parents[2] / "agent" / "src" / "AstraAgent.Service"


async def _device(session_factory, org_id, host):
    async with session_factory() as s:
        d = Device(org_id=org_id, hostname=host, machine_id=host, os_version="Windows 11",
                   agent_version="0.14.0", token_hash=hash_opaque_token(host), last_seen_at=utcnow())
        s.add(d)
        await s.commit()
        return d


async def _password_task(session_factory, org_id, device_id, *, age=timedelta(minutes=5)):
    async with session_factory() as s:
        t = RemediationTask(
            org_id=org_id, device_id=device_id, action_id="create_local_user", tier="admin_only",
            reason="new joiner", source=RemediationSource.USER, status=RemediationStatus.SUCCEEDED,
            completed_at=utcnow() - age,
            result={"output": "Created local account 'jdoe'.\n\nOne-time password: Xy7-secret-pw\n\nShare it once."})
        s.add(t)
        await s.commit()


# ── H4: one-time passwords ────────────────────────────────────────────────────────────

async def test_one_time_password_only_for_admins_and_only_for_a_day(
        client, admin_headers, admin_user, session_factory):
    dev = await _device(session_factory, admin_user.org_id, "PC-1")
    await _password_task(session_factory, admin_user.org_id, dev.id)
    await _create_user(session_factory, admin_user.org_id, "tech@acme.com", ADMIN_PASSWORD, UserRole.TECHNICIAN)
    tech = await auth_headers(client, "tech@acme.com", ADMIN_PASSWORD)

    out = lambda r: r.json()["items"][0]["result"]["output"]
    assert "Xy7-secret-pw" in out(await client.get("/api/v1/remediations", headers=admin_headers))
    tech_view = out(await client.get("/api/v1/remediations", headers=tech))
    assert "Xy7-secret-pw" not in tech_view and "One-time password: [hidden" in tech_view

    async with session_factory() as s:
        task = (await s.execute(select(RemediationTask))).scalar_one()
        task.completed_at = utcnow() - timedelta(hours=25)
        await s.commit()
    assert "Xy7-secret-pw" not in out(await client.get("/api/v1/remediations", headers=admin_headers))


# ── H5: the AI's device tools stay on the user's own PC ───────────────────────────────

async def test_ai_device_tools_refuse_other_pcs_without_fleet_access(session_factory, admin_user):
    mine = await _device(session_factory, admin_user.org_id, "ASHA-PC")
    await _device(session_factory, admin_user.org_id, "CEO-LAPTOP")

    async def call(name, args, acting):
        async with session_factory() as s:
            return json.loads(await dispatch_tool(session=s, org_id=admin_user.org_id, name=name,
                                                  tool_input=args, acting_device_id=acting))

    for tool in ("get_device_telemetry", "get_device_events"):
        refused = await call(tool, {"hostname": "CEO-LAPTOP"}, mine.id)
        assert "own computer" in refused["error"]
        # A plain portal user has no device of their own at all.
        assert "own computer" in (await call(tool, {"hostname": "ASHA-PC"}, None))["error"]
    assert [d["hostname"] for d in await call("list_devices", {}, mine.id)] == ["ASHA-PC"]
    assert await call("list_devices", {}, None) == []


# ── H6 / M5: view-as and the platform console ─────────────────────────────────────────

async def test_view_as_cannot_take_the_key_and_console_follows_the_window(
        client, admin_headers, admin_user, regular_user, session_factory, other_org):
    async with session_factory() as s:
        (await s.get(User, admin_user.id)).is_platform_admin = True
        await s.commit()
    oid = other_org.id
    # Window closed: the per-org lists are refused (counts stay on the overview).
    for section in ("users", "devices", "remediation", "assets"):
        r = await client.get(f"/api/v1/platform/organizations/{oid}/{section}", headers=admin_headers)
        assert r.status_code == 403, section

    async with session_factory() as s:
        (await s.get(Organization, oid)).support_access_until = utcnow() + timedelta(hours=1)
        await s.commit()
    r = await client.get(f"/api/v1/platform/organizations/{oid}/users", headers=admin_headers)
    assert r.status_code == 200
    async with session_factory() as s:
        audit = (await s.execute(select(AuditLog).where(AuditLog.action == "platform.org_data_view"))).scalar_one()
        assert audit.org_id == oid and audit.detail == {"section": "users", "by": admin_user.email}

    vt = await client.post(f"/api/v1/platform/organizations/{oid}/view-token", headers=admin_headers)
    view = {"Authorization": f"Bearer {vt.json()['access_token']}"}
    assert (await client.get("/api/v1/devices", headers=view)).status_code == 200      # reads still work
    assert (await client.get("/api/v1/devices/installer", headers=view)).status_code == 403
    other = await _create_user(session_factory, oid, "p@globex.com", ADMIN_PASSWORD, UserRole.USER)
    assert (await client.get(f"/api/v1/users/{other.id}/personal-data/export", headers=view)).status_code == 403


# ── H7 + M6: erase / export can't be steered by a self-chosen name ────────────────────

async def test_self_chosen_name_does_not_rewrite_other_peoples_audit(
        client, admin_headers, admin_user, regular_user, user_headers, session_factory):
    async with session_factory() as s:
        s.add(AuditLog(org_id=admin_user.org_id, actor_id=admin_user.id, action="device.update",
                       target_type="device", target_id="x", detail={"note": "approved by Ravi"}))
        await s.commit()
    # The leaver renames themselves to a word that appears in other people's entries.
    assert (await client.patch("/api/v1/auth/me", headers=user_headers,
                               json={"full_name": "approved"})).status_code == 200
    r = await client.get(f"/api/v1/users/{regular_user.id}/personal-data/export", headers=admin_headers)
    assert all(a["action"] != "device.update" for a in r.json()["audit_entries"])

    assert (await client.delete(f"/api/v1/users/{regular_user.id}", headers=admin_headers)).status_code == 204
    async with session_factory() as s:
        entry = (await s.execute(select(AuditLog).where(AuditLog.action == "device.update"))).scalar_one()
        assert entry.detail == {"note": "approved by Ravi"}


async def test_export_carries_no_task_results(client, admin_headers, admin_user, session_factory):
    tech = await _create_user(session_factory, admin_user.org_id, "tech@acme.com", ADMIN_PASSWORD, UserRole.TECHNICIAN)
    dev = await _device(session_factory, admin_user.org_id, "PC-2")
    async with session_factory() as s:
        s.add(RemediationTask(org_id=admin_user.org_id, device_id=dev.id, action_id="reset_local_password",
                              tier="admin_only", reason="r", source=RemediationSource.USER,
                              approved_by_user_id=tech.id, params={"username": "someone"},
                              result={"output": "Temporary password: Zz9-other-pw"}))
        await s.commit()
    data = (await client.get(f"/api/v1/users/{tech.id}/personal-data/export", headers=admin_headers)).json()
    assert data["remediations"] and "result" not in data["remediations"][0]
    assert "Zz9-other-pw" not in json.dumps(data)


# ── M7 + low: deletes that would lock operators out ───────────────────────────────────

async def test_operator_cannot_delete_own_org_and_admins_cannot_delete_operators(
        client, admin_headers, admin_user, session_factory):
    async with session_factory() as s:
        (await s.get(User, admin_user.id)).is_platform_admin = True
        await s.commit()
    r = await client.delete(f"/api/v1/platform/organizations/{admin_user.org_id}", headers=admin_headers)
    assert r.status_code == 409

    other_admin = await _create_user(session_factory, admin_user.org_id, "a2@acme.com", ADMIN_PASSWORD, UserRole.ADMIN)
    h2 = await auth_headers(client, "a2@acme.com", ADMIN_PASSWORD)
    assert (await client.delete(f"/api/v1/users/{admin_user.id}", headers=h2)).status_code == 409
    assert other_admin.id


# ── A2: catalog, audit, input handling ────────────────────────────────────────────────

def test_agent_catalog_matches():
    text = (AGENT / "Remediation" / "PackageInstaller.cs").read_text(encoding="utf-8")
    body = re.search(r"HashSet<string> Catalog = new\(StringComparer\.Ordinal\)\s*\{(.*?)\};", text, re.DOTALL)
    assert body, "Catalog not found in PackageInstaller.cs"
    assert set(re.findall(r'"([^"]+)"', body.group(1))) == set(CATALOG)
    assert not any("anydesk" in k.lower() or "teamviewer" in k.lower() for k in CATALOG)


async def test_package_id_must_be_a_string_and_audit_names_the_target(
        client, admin_headers, admin_user, session_factory):
    dev = await _device(session_factory, admin_user.org_id, "PC-3")
    r = await client.post("/api/v1/remediations", headers=admin_headers, json={
        "device_id": str(dev.id), "action_id": "install_package", "params": {"package_id": ["Google.Chrome"]},
        "reason": "r"})
    assert r.status_code == 400

    r = await client.post("/api/v1/deployments/install", headers=admin_headers, json={
        "package_id": "7zip.7zip", "device_ids": [str(dev.id)], "group_ids": [], "exclude_device_ids": [],
        "reason": "tools"})
    assert r.status_code in (200, 201), r.text
    async with session_factory() as s:
        dep = (await s.execute(select(AuditLog).where(AuditLog.action == "deployment.create"))).scalar_one()
        assert dep.target_id not in (None, "None")
        created = (await s.execute(select(AuditLog).where(AuditLog.action == "remediation.create"))).scalars().all()
        assert created[-1].detail["package_id"] == "7zip.7zip"


async def test_assistant_can_never_create_admin_only_tasks(session_factory, admin_user):
    import pytest

    from app.services.remediation.service import RemediationError, RemediationService
    dev = await _device(session_factory, admin_user.org_id, "PC-4")
    async with session_factory() as s:
        device = await s.get(Device, dev.id)
        with pytest.raises(RemediationError, match="only be started by a person"):
            await RemediationService(s).create_task(
                org_id=admin_user.org_id, device=device, action_id="create_local_user",
                params={"username": "x1"}, reason="r", source=RemediationSource.ASSISTANT, actor_user_id=None)
