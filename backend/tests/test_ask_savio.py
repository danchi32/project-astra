"""L3 — Ask SAVIO: wider evidence for IT staff, nothing extra for an employee's tray chat."""
import json
import uuid
from datetime import date, timedelta

from app.core.security import hash_opaque_token
from app.models import (
    Asset,
    Device,
    DeviceInstalledApp,
    DeviceService,
    DeviceWindowsUpdate,
    User,
)
from app.models.base import utcnow
from app.services.ai import fleet_tools
from app.services.ai.cognitive import CognitiveEngine
from app.services.ai.provider import LLMResponse
from app.services.ai.tools import dispatch_tool


class Recorder:
    def __init__(self) -> None:
        self.tools: list = []

    async def generate(self, *, system, messages, tools):
        self.tools.append([t["name"] for t in tools])
        return LLMResponse(text="ok")


async def _seed(session_factory, org_id):
    """Two PCs: ASHA-PC (Defender stopped, ChatGPT per-user, a failed update) and RAVI-PC."""
    async with session_factory() as s:
        asha = Device(org_id=org_id, hostname="ASHA-PC", machine_id="a1", os_version="Windows 11",
                      agent_version="0.14.0", token_hash=hash_opaque_token("t-a"), last_seen_at=utcnow())
        ravi = Device(org_id=org_id, hostname="RAVI-PC", machine_id="r1", os_version="Windows 11",
                      agent_version="0.14.0", token_hash=hash_opaque_token("t-r"), last_seen_at=utcnow())
        s.add_all([asha, ravi])
        await s.flush()
        now = utcnow()
        s.add_all([
            DeviceService(org_id=org_id, device_id=asha.id, name="WinDefend", display_name="Defender",
                          status="Stopped", start_type="Auto", collected_at=now),
            DeviceService(org_id=org_id, device_id=ravi.id, name="WinDefend", display_name="Defender",
                          status="Running", start_type="Auto", collected_at=now),
            DeviceInstalledApp(org_id=org_id, device_id=asha.id, name="ChatGPT", scope="user",
                               user_name="ACME\\asha", collected_at=now),
            DeviceInstalledApp(org_id=org_id, device_id=asha.id, name="Google Chrome", collected_at=now),
            DeviceWindowsUpdate(org_id=org_id, device_id=asha.id, kb_article_id="KB5040442",
                                title="Cumulative Update", state="failed", error_code="0x80070005",
                                collected_at=now),
        ])
        user = User(org_id=org_id, email="priya@acme.com", full_name="Priya Sharma",
                    hashed_password="x", role="user")
        s.add(user)
        await s.flush()
        soon = (date.today() + timedelta(days=20)).isoformat()
        later = (date.today() + timedelta(days=400)).isoformat()
        s.add_all([
            Asset(org_id=org_id, name="Priya's ThinkPad", assigned_to_user_id=user.id,
                  serial_number="PW07MN54", warranty_expiry=soon, device_id=asha.id),
            Asset(org_id=org_id, name="Spare Dell", warranty_expiry=later),
        ])
        await s.commit()
        return asha.id, ravi.id


async def _call(session_factory, org_id, name, args, *, acting=None, fleet=False):
    async with session_factory() as s:
        return json.loads(await dispatch_tool(session=s, org_id=org_id, name=name, tool_input=args,
                                              acting_device_id=acting, fleet_access=fleet))


async def test_staff_see_fleet_tools_end_users_do_not(session_factory, admin_user):
    for fleet, expect in ((True, True), (False, False)):
        rec = Recorder()
        async with session_factory() as s:
            await CognitiveEngine(s, rec).run(org_id=admin_user.org_id, history=[],
                                              user_message="which PCs have Defender off?",
                                              fleet_access=fleet)
        names = set(rec.tools[0])
        assert fleet_tools.DEVICE_TOOLS <= names
        assert (fleet_tools.FLEET_TOOLS <= names) is expect


async def test_tray_chat_only_answers_for_its_own_device(session_factory, admin_user):
    org = admin_user.org_id
    asha, _ = await _seed(session_factory, org)
    own = await _call(session_factory, org, "get_installed_apps", {"hostname": "asha-pc"}, acting=asha)
    assert {a["name"] for a in own["apps"]} == {"ChatGPT", "Google Chrome"}
    assert next(a for a in own["apps"] if a["name"] == "ChatGPT")["user"] == "ACME\\asha"

    other = await _call(session_factory, org, "get_installed_apps", {"hostname": "RAVI-PC"}, acting=asha)
    assert "own device" in other["error"]

    fleet = await _call(session_factory, org, "fleet_summary", {}, acting=asha)
    assert "IT staff" in fleet["error"]

    listed = await _call(session_factory, org, "list_devices", {}, acting=asha)
    assert [d["hostname"] for d in listed] == ["ASHA-PC"]


async def test_fleet_summary_names_the_failing_machines(session_factory, admin_user):
    org = admin_user.org_id
    await _seed(session_factory, org)
    out = await _call(session_factory, org, "fleet_summary", {}, fleet=True)
    defender = out["checks"]["Microsoft Defender running"]
    assert defender["fail"] == 1 and defender["pass"] == 1
    assert defender["failing"][0].startswith("ASHA-PC")


async def test_updates_and_compliance_for_one_device(session_factory, admin_user):
    org = admin_user.org_id
    await _seed(session_factory, org)
    upd = await _call(session_factory, org, "get_windows_updates", {"hostname": "ASHA-PC"}, fleet=True)
    assert upd["outstanding"] == [{"kb": "KB5040442", "title": "Cumulative Update",
                                   "state": "failed", "error_code": "0x80070005"}]
    comp = await _call(session_factory, org, "get_device_compliance", {"hostname": "ASHA-PC"}, fleet=True)
    checks = {c["check"]: c["status"] for c in comp["checks"]}
    assert checks["Microsoft Defender running"] == "fail"


async def test_find_assets_by_warranty_and_by_person(session_factory, admin_user):
    org = admin_user.org_id
    await _seed(session_factory, org)
    soon = await _call(session_factory, org, "find_assets", {"warranty_expiring_within_days": 30}, fleet=True)
    assert [a["name"] for a in soon["assets"]] == ["Priya's ThinkPad"]
    assert soon["assets"][0]["device"] == "ASHA-PC"

    priya = await _call(session_factory, org, "find_assets", {"text": "priya"}, fleet=True)
    assert priya["assets"][0]["assigned_to"] == "Priya Sharma"


async def test_no_cross_org_leak(session_factory, admin_user):
    await _seed(session_factory, admin_user.org_id)
    other_org = uuid.uuid4()
    out = await _call(session_factory, other_org, "get_installed_apps", {"hostname": "ASHA-PC"}, fleet=True)
    assert "No device found" in out["error"]
    assets = await _call(session_factory, other_org, "find_assets", {}, fleet=True)
    assert assets["assets"] == []


async def test_portal_role_decides_fleet_access(client, admin_headers, user_headers, monkeypatch):
    """Admins (and technicians) get fleet evidence; a plain portal user does not."""
    import app.services.conversations as conv

    seen: list[bool] = []

    class Spy(CognitiveEngine):
        async def run(self, **kw):
            seen.append(kw.get("fleet_access", False))
            return await super().run(**kw)

    monkeypatch.setattr(conv, "CognitiveEngine", Spy)
    # Different questions: the same one twice in one org is answered from the semantic cache
    # and never reaches the engine.
    for headers, question in ((admin_headers, "which PCs have Defender off?"),
                              (user_headers, "whose laptop warranty ends this month?")):
        cid = (await client.post("/api/v1/conversations", json={"title": "t"}, headers=headers)).json()["id"]
        r = await client.post(f"/api/v1/conversations/{cid}/messages",
                              json={"content": question}, headers=headers)
        assert r.status_code in (200, 201), r.text
    assert seen == [True, False]
