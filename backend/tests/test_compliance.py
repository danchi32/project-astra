from app.core.security import hash_opaque_token
from app.models import Device, DeviceInstalledApp, DeviceWindowsUpdate
from app.models.base import utcnow


class _Org:
    """Minimal stand-in carrying just the org id our seed helper needs."""

    def __init__(self, org_id):
        self.id = org_id


async def _make_device(session_factory, org, hostname="LSI-COMP", machine="mach-comp"):
    """Seed one device with a pending update and uTorrent installed."""
    async with session_factory() as session:
        device = Device(
            org_id=org.id, hostname=hostname, machine_id=machine,
            os_version="Windows 11", agent_version="0.6.4",
            token_hash=hash_opaque_token(f"tok-{machine}"), last_seen_at=utcnow(),
        )
        session.add(device)
        await session.flush()
        session.add(DeviceWindowsUpdate(
            org_id=org.id, device_id=device.id, kb_article_id="KB5040442",
            title="Cumulative Update", state="pending", collected_at=utcnow(),
        ))
        session.add(DeviceInstalledApp(
            org_id=org.id, device_id=device.id, name="uTorrent", collected_at=utcnow(),
        ))
        await session.commit()
        return device.id


async def test_summary_empty_org(client, admin_headers):
    resp = await client.get("/api/v1/compliance/summary", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_devices"] == 0
    assert body["score"] == 100


async def test_device_fails_patch_check(client, admin_headers, admin_user, session_factory):
    await _make_device(session_factory, _Org(admin_user.org_id))
    resp = await client.get("/api/v1/compliance/devices", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    rows = resp.json()["items"]
    assert len(rows) == 1
    patch = next(c for c in rows[0]["checks"] if c["key"] == "patch")
    assert patch["status"] == "fail"
    assert patch["fix_action_id"] == "windows_update_install"


async def test_banned_software_crud_and_detection(client, admin_headers, admin_user, session_factory):
    await _make_device(session_factory, _Org(admin_user.org_id))

    add = await client.post(
        "/api/v1/compliance/banned-software", json={"name": "uTorrent"}, headers=admin_headers)
    assert add.status_code == 201, add.text
    banned_id = add.json()["id"]

    dup = await client.post(
        "/api/v1/compliance/banned-software", json={"name": "utorrent"}, headers=admin_headers)
    assert dup.status_code == 409

    rows = (await client.get("/api/v1/compliance/devices", headers=admin_headers)).json()["items"]
    chk = next(c for c in rows[0]["checks"] if c["key"] == "no_banned_software")
    assert chk["status"] == "fail"
    assert "uTorrent" in chk["detail"]

    rm = await client.delete(
        f"/api/v1/compliance/banned-software/{banned_id}", headers=admin_headers)
    assert rm.status_code == 204
    rows = (await client.get("/api/v1/compliance/devices", headers=admin_headers)).json()["items"]
    assert all(c["key"] != "no_banned_software" for c in rows[0]["checks"])


async def test_banned_software_add_requires_admin(client, user_headers):
    resp = await client.post(
        "/api/v1/compliance/banned-software", json={"name": "Steam"}, headers=user_headers)
    assert resp.status_code == 403


async def test_compliance_requires_staff(client, user_headers):
    resp = await client.get("/api/v1/compliance/summary", headers=user_headers)
    assert resp.status_code == 403


# ── Update states ──────────────────────────────────────────────────────────
#
# Modelled on a real device: two updates installed and waiting on a reboot, and one whose
# download keeps failing with 0x80244018. All three used to be stored as is_installed=False
# and rendered as "Pending", so the portal contradicted the Windows Update page the user was
# looking at on the machine itself.


async def _device_with_updates(session_factory, org_id, host, machine, updates):
    from app.models import Device, DeviceWindowsUpdate
    from app.core.security import hash_opaque_token
    from app.models.base import utcnow

    async with session_factory() as session:
        device = Device(
            org_id=org_id, hostname=host, machine_id=machine,
            os_version="Windows 11 Enterprise 25H2 (build 26200.8893)",
            agent_version="0.7.4", token_hash=hash_opaque_token(f"tok-{machine}"),
            last_seen_at=utcnow(),
        )
        session.add(device)
        await session.flush()
        for kb, state, code in updates:
            session.add(DeviceWindowsUpdate(
                org_id=org_id, device_id=device.id, kb_article_id=kb,
                title=f"{kb} update", state=state, error_code=code, collected_at=utcnow(),
            ))
        await session.commit()
        return device.id


async def test_awaiting_restart_is_not_reported_as_unpatched(
    client, admin_headers, admin_user, session_factory
):
    """A device that installed its updates and owes a reboot is one restart from compliant.
    Saying "2 update(s) pending" sends someone to reinstall what is already installed."""
    await _device_with_updates(
        session_factory, admin_user.org_id, "REBOOT-PC", "m-reboot",
        [("KB5094126", "pending_restart", None), ("KB5100998", "pending_restart", None)],
    )
    resp = await client.get("/api/v1/compliance/devices", headers=admin_headers)
    device = next(d for d in resp.json()["items"] if d["hostname"] == "REBOOT-PC")
    patch = next(c for c in device["checks"] if c["key"] == "patch")

    assert patch["status"] == "fail"          # not applied yet, so still not compliant
    assert "restart" in patch["detail"].lower()
    assert "pending" not in patch["detail"].lower()


async def test_a_failed_update_reports_its_error_code(
    client, admin_headers, admin_user, session_factory
):
    """"Failed" on its own cannot be acted on. The code is what distinguishes a transient
    blip from a proxy blocking the update endpoint across the whole fleet."""
    await _device_with_updates(
        session_factory, admin_user.org_id, "FAIL-PC", "m-fail",
        [("KB5007651", "failed", "0x80244018")],
    )
    resp = await client.get("/api/v1/compliance/devices", headers=admin_headers)
    device = next(d for d in resp.json()["items"] if d["hostname"] == "FAIL-PC")
    patch = next(c for c in device["checks"] if c["key"] == "patch")

    assert patch["status"] == "fail"
    assert "KB5007651" in patch["detail"]
    assert "0x80244018" in patch["detail"]


async def test_restart_pending_offers_no_reinstall_but_says_why(
    client, admin_headers, admin_user, session_factory
):
    """Fleet Issues must not offer to push an install for something already installed —
    it would run, report success, and change nothing."""
    await _device_with_updates(
        session_factory, admin_user.org_id, "FLEET-REBOOT", "m-fleet-reboot",
        [("KB5094126", "pending_restart", None)],
    )
    resp = await client.get("/api/v1/fleet/issues", headers=admin_headers)
    issue = next(
        i for i in resp.json()["issues"] if i["key"] == "update:pending_restart:KB5094126"
    )
    assert issue["fix_action_id"] is None
    assert "reboot" in issue["fix_note"].lower()


async def test_is_installed_cannot_be_set_directly():
    """The boolean is a projection of state. Accepting it as an input would let a caller
    store a row claiming an update is installed while its state says it failed."""
    import pytest
    from app.models import DeviceWindowsUpdate

    with pytest.raises(TypeError, match="derived from state"):
        DeviceWindowsUpdate(kb_article_id="KB1", title="t", is_installed=True)
