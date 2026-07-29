from app.core.security import hash_opaque_token
from app.models import Device, DeviceWindowsUpdate
from app.models.base import utcnow


class _Org:
    def __init__(self, org_id):
        self.id = org_id


async def _device_with_pending_update(session_factory, org_id, host, machine, kb="KB5040442"):
    async with session_factory() as session:
        device = Device(
            org_id=org_id, hostname=host, machine_id=machine,
            os_version="Windows 11", agent_version="0.6.4",
            token_hash=hash_opaque_token(f"tok-{machine}"), last_seen_at=utcnow(),
        )
        session.add(device)
        await session.flush()
        session.add(DeviceWindowsUpdate(
            org_id=org_id, device_id=device.id, kb_article_id=kb,
            title="Cumulative Update", is_installed=False, collected_at=utcnow(),
        ))
        await session.commit()
        return device.id


async def test_fleet_issues_group_update_across_devices(client, admin_headers, admin_user, session_factory):
    org_id = admin_user.org_id
    await _device_with_pending_update(session_factory, org_id, "PC-1", "m1")
    await _device_with_pending_update(session_factory, org_id, "PC-2", "m2")

    resp = await client.get("/api/v1/fleet/issues", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    issues = resp.json()["issues"]
    kb_issue = next(i for i in issues if i["key"] == "update:KB5040442")
    assert len(kb_issue["affected"]) == 2                       # both devices grouped
    assert kb_issue["fix_action_id"] == "windows_update_install"
    assert kb_issue["fix_params"] == {"kb_article_id": "KB5040442"}


async def test_bulk_remediate_queues_all(client, admin_headers, admin_user, session_factory):
    org_id = admin_user.org_id
    d1 = await _device_with_pending_update(session_factory, org_id, "PC-1", "m1")
    d2 = await _device_with_pending_update(session_factory, org_id, "PC-2", "m2")

    resp = await client.post("/api/v1/fleet/remediate", headers=admin_headers, json={
        "device_ids": [str(d1), str(d2)],
        "action_id": "windows_update_install",
        "params": {"kb_article_id": "KB5040442"},
        "reason": "Patch all outdated devices from Fleet Issues",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["queued"] == 2
    assert body["failed"] == 0


async def test_bulk_remediate_rejects_other_org_devices(client, admin_headers, other_org, session_factory):
    other_id = await _device_with_pending_update(session_factory, other_org.id, "GLOBEX", "gm1")
    resp = await client.post("/api/v1/fleet/remediate", headers=admin_headers, json={
        "device_ids": [str(other_id)],
        "action_id": "windows_update_install",
        "reason": "should not touch another org",
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["failed"] == 1
    assert resp.json()["queued"] == 0


async def test_fleet_requires_staff(client, user_headers):
    assert (await client.get("/api/v1/fleet/issues", headers=user_headers)).status_code == 403
