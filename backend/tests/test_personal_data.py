"""Z2 — export and erase everything SAVIO holds about one person."""
from datetime import date

from sqlalchemy import func, select

from app.core.security import hash_opaque_token
from app.models import (
    ActivitySample,
    Asset,
    AssetEvent,
    AssetEventType,
    AuditLog,
    Conversation,
    DailyUserSummary,
    Device,
    DeviceInstalledApp,
    DeviceSession,
    Message,
    MessageRole,
    RemediationSource,
    RemediationTask,
    User,
)
from app.models.base import utcnow
from app.services.personal_data import pseudonym

EMAIL = "asha.verma@acme.com"


async def _seed(session_factory, org_id, admin_id):
    async with session_factory() as s:
        now = utcnow()
        asha = User(org_id=org_id, email=EMAIL, full_name="Asha Verma", hashed_password=None)
        dev = Device(org_id=org_id, hostname="ASHA-LAPTOP", machine_id="z2-1", os_version="Windows 11",
                     agent_version="0.14.0", token_hash=hash_opaque_token("z2"), last_seen_at=now)
        s.add_all([asha, dev])
        await s.flush()
        conv = Conversation(org_id=org_id, user_id=asha.id, title="VPN not connecting")
        s.add(conv)
        await s.flush()
        asset = Asset(org_id=org_id, name="Asha's laptop", assigned_to_user_id=asha.id)
        s.add(asset)
        await s.flush()
        s.add_all([
            Message(conversation_id=conv.id, role=MessageRole.USER, content="My VPN drops every hour"),
            AssetEvent(org_id=org_id, asset_id=asset.id, event_type=AssetEventType.ASSIGNED, actor_id=admin_id,
                       user_id=asha.id, from_value=None, to_value="Asha Verma", occurred_at=now),
            # Tracker + sessions + profile apps under her Windows name; one row for someone else.
            ActivitySample(org_id=org_id, device_id=dev.id, username="ACME\\asha", kind="logon", occurred_at=now),
            ActivitySample(org_id=org_id, device_id=dev.id, username="ACME\\ashadeep", kind="logon", occurred_at=now),
            ActivitySample(org_id=org_id, device_id=dev.id, username="ACME\\ganasha", kind="logon", occurred_at=now),
            DailyUserSummary(org_id=org_id, device_id=dev.id, username="ACME\\asha", day=date.today()),
            DeviceSession(org_id=org_id, device_id=dev.id, session_id=1, username="ACME\\asha",
                          state="active", connection="console"),
            DeviceInstalledApp(org_id=org_id, device_id=dev.id, name="ChatGPT", scope="user",
                               user_name="ACME\\asha", collected_at=now),
            RemediationTask(org_id=org_id, device_id=dev.id, action_id="flush_dns", tier="automatic",
                            reason="asked", source=RemediationSource.USER, requested_by_user_id=asha.id),
            AuditLog(org_id=org_id, actor_id=admin_id, action="user.update", target_type="user",
                     target_id=str(asha.id), detail={"email": EMAIL, "note": "Asha Verma moved to Pune"}),
            AuditLog(org_id=org_id, actor_id=admin_id, action="device.local_user_disable",
                     target_type="device", target_id=str(dev.id),
                     detail={"username": "ACME\\asha", "also": "ACME\\ashadeep"}),
        ])
        await s.commit()
        return asha.id


async def test_summary_export_then_erase(client, admin_headers, admin_user, session_factory):
    uid = await _seed(session_factory, admin_user.org_id, admin_user.id)
    base = f"/api/v1/users/{uid}/personal-data"

    r = await client.get(base, headers=admin_headers)
    assert r.status_code == 200, r.text
    # Suggested from email local part / name; ashadeep matches "asha" too — the admin decides.
    assert "ACME\\asha" in r.json()["windows_username_candidates"]

    r = await client.get(base, params={"windows_username": "asha"}, headers=admin_headers)
    c = r.json()["counts"]
    assert (c["conversations"], c["assets_assigned"], c["activity_samples"], c["daily_user_summary"],
            c["device_sessions"], c["apps_in_their_profile"], c["remediations"]) == (1, 1, 1, 1, 1, 1, 1)
    assert c["audit_entries"] == 2

    r = await client.get(base + "/export", params={"windows_username": "asha"}, headers=admin_headers)
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    data = r.json()
    assert data["account"]["email"] == EMAIL and "hashed_password" not in data["account"]
    assert data["conversations"][0]["messages"][0]["content"] == "My VPN drops every hour"
    assert [a["username"] for a in data["activity_samples"]] == ["ACME\\asha"]

    # Wrong confirmation: nothing happens.
    r = await client.post(base + "/erase", json={"windows_usernames": ["asha"], "confirm_email": "x@y.com"},
                          headers=admin_headers)
    assert r.status_code == 409
    r = await client.post(base + "/erase", json={"windows_usernames": ["asha"], "confirm_email": EMAIL.upper()},
                          headers=admin_headers)
    assert r.status_code == 200, r.text
    alias = pseudonym(uid)
    assert r.json()["person"] == alias

    async with session_factory() as s:
        n = lambda m, *w: s.scalar(select(func.count()).select_from(m).where(*w))
        assert await s.get(User, uid) is None
        assert await n(Conversation) == 0 and await n(Message) == 0
        assert await n(ActivitySample) == 2                       # ashadeep's and ganasha's survive
        assert await n(DailyUserSummary) == 0 and await n(DeviceSession) == 0
        assert await n(DeviceInstalledApp) == 0
        asset = (await s.execute(select(Asset))).scalar_one()
        assert asset.assigned_to_user_id is None                  # asset kept, unassigned
        ev = (await s.execute(select(AssetEvent))).scalar_one()
        assert ev.user_id is None and ev.to_value == alias
        # The security record of what she asked for stays.
        assert (await s.execute(select(RemediationTask))).scalar_one().requested_by_user_id == uid
        audits = {a.action: a.detail for a in (await s.execute(select(AuditLog))).scalars()}
        assert audits["user.update"] == {"email": alias, "note": f"{alias} moved to Pune"}
        assert audits["device.local_user_disable"] == {"username": f"ACME\\{alias}", "also": "ACME\\ashadeep"}
        # Export and erase are audited, and the erase entry never names her.
        assert "user.personal_data_export" in audits
        assert EMAIL not in str(audits["user.personal_data_erase"])
        assert audits["user.personal_data_erase"]["person"] == alias


async def test_guards(client, admin_headers, user_headers, admin_user, regular_user, other_org_user):
    me = f"/api/v1/users/{admin_user.id}/personal-data"
    r = await client.post(me + "/erase", json={"confirm_email": admin_user.email}, headers=admin_headers)
    assert r.status_code == 409                                    # not yourself
    other = f"/api/v1/users/{other_org_user.id}/personal-data"
    assert (await client.get(other, headers=admin_headers)).status_code == 404
    assert (await client.get(other + "/export", headers=admin_headers)).status_code == 404
    plain = f"/api/v1/users/{regular_user.id}/personal-data"
    assert (await client.get(plain, headers=user_headers)).status_code == 403
    assert (await client.get(plain + "/export", headers=user_headers)).status_code == 403


async def test_plain_delete_no_longer_leaves_the_email_behind(client, admin_headers, admin_user, session_factory):
    # G10: the Users page's Delete used to write {"email": ...} into the audit log and leave
    # assets pointing at a dead id.
    uid = await _seed(session_factory, admin_user.org_id, admin_user.id)
    r = await client.delete(f"/api/v1/users/{uid}", headers=admin_headers)
    assert r.status_code == 204, r.text
    alias = pseudonym(uid)
    async with session_factory() as s:
        assert await s.get(User, uid) is None
        assert (await s.execute(select(Asset))).scalar_one().assigned_to_user_id is None
        audits = {a.action: a.detail for a in (await s.execute(select(AuditLog))).scalars()}
        assert audits["user.delete"] == {"person": alias}
        assert audits["user.update"]["email"] == alias
        assert EMAIL not in str(audits)
        # No Windows usernames given, so device-side data is untouched — that needs the full erase.
        assert await s.scalar(select(func.count()).select_from(ActivitySample)) == 3
