"""The dashboard's one payload.

The two things worth pinning: that it leads with things a person can act on, and that it
scores the fleet once. The second is invisible when it regresses — the page still renders,
just twice as expensively — so it is asserted rather than trusted.
"""
from app.core.security import hash_opaque_token
from app.models import (
    Device,
    DeviceWindowsUpdate,
    RemediationSource,
    RemediationTask,
)
from app.models.base import utcnow


async def _device(session, org_id, hostname, machine, *, last_seen=None):
    device = Device(
        org_id=org_id, hostname=hostname, machine_id=machine,
        os_version="Windows 11 Enterprise 25H2 (build 26200.8893)",
        agent_version="0.7.4", token_hash=hash_opaque_token(machine),
        last_seen_at=last_seen if last_seen is not None else utcnow(),
    )
    session.add(device)
    await session.flush()
    return device


async def test_a_quiet_fleet_asks_nothing_of_you(client, admin_headers):
    """An empty list, not a padded one. A dashboard that always shows five items is one
    nobody reads on the day it matters."""
    body = (await client.get("/api/v1/dashboard/overview", headers=admin_headers)).json()
    assert body["needs_you"] == []
    assert body["top_issues"] == []


async def test_it_leads_with_what_someone_can_act_on(
    client, admin_headers, admin_user, session_factory
):
    async with session_factory() as session:
        d = await _device(session, admin_user.org_id, "OVW-1", "ovw-1")
        session.add(RemediationTask(
            org_id=admin_user.org_id, device_id=d.id, action_id="office_repair",
            tier="approval_required", status="pending_approval", reason="needs a human",
            source=RemediationSource.USER,
        ))
        session.add(DeviceWindowsUpdate(
            org_id=admin_user.org_id, device_id=d.id, kb_article_id="KB5007651",
            title="Security platform update", state="failed", error_code="0x80244018",
            collected_at=utcnow(),
        ))
        await session.commit()

    body = (await client.get("/api/v1/dashboard/overview", headers=admin_headers)).json()
    keys = [a["key"] for a in body["needs_you"]]
    assert "approvals" in keys
    assert "failed_updates" in keys

    approval = next(a for a in body["needs_you"] if a["key"] == "approvals")
    # Phrased as the decision, and pointing at where the decision is made.
    assert "approval" in approval["title"].lower()
    assert approval["href"] == "/self-healing"


async def test_restart_pending_is_its_own_item_not_lumped_into_pending(
    client, admin_headers, admin_user, session_factory
):
    """An update that is installed and owed a reboot needs a different response from one
    that was never installed. Rolling them together is what made the portal offer to
    reinstall updates that were already on the machine."""
    async with session_factory() as session:
        d = await _device(session, admin_user.org_id, "OVW-2", "ovw-2")
        session.add(DeviceWindowsUpdate(
            org_id=admin_user.org_id, device_id=d.id, kb_article_id="KB5094126",
            title="Cumulative update", state="pending_restart", collected_at=utcnow(),
        ))
        await session.commit()

    body = (await client.get("/api/v1/dashboard/overview", headers=admin_headers)).json()
    assert body["patch"]["awaiting_restart"] == 1
    assert body["patch"]["pending"] == 0
    assert "awaiting_restart" in [a["key"] for a in body["needs_you"]]


async def test_the_fleet_is_scored_once_per_page_load(
    client, admin_headers, admin_user, session_factory, monkeypatch
):
    """The compliance summary and the ranked issues both come from scoring every device.
    Fetching them separately would do that work twice — cheap at ten devices, the dominant
    cost of the home screen at two thousand, and completely invisible from the rendered page.
    """
    async with session_factory() as session:
        for i in range(3):
            await _device(session, admin_user.org_id, f"OVW-S{i}", f"ovw-s{i}")
        await session.commit()

    import app.services.compliance as comp

    calls = 0
    original = comp.ComplianceService._evaluate

    async def counting(self, **kwargs):
        nonlocal calls
        calls += 1
        return await original(self, **kwargs)

    monkeypatch.setattr(comp.ComplianceService, "_evaluate", counting)

    resp = await client.get("/api/v1/dashboard/overview", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert calls == 1, f"the fleet was scored {calls} times to render one dashboard"


async def test_silent_devices_are_surfaced(
    client, admin_headers, admin_user, session_factory
):
    """A device that stopped reporting is the one failure that makes every other number on
    the page stale, so it gets its own line rather than being inferred from a chart."""
    from datetime import timedelta

    async with session_factory() as session:
        await _device(session, admin_user.org_id, "GONE", "gone-m",
                      last_seen=utcnow() - timedelta(days=3))
        await session.commit()

    body = (await client.get("/api/v1/dashboard/overview", headers=admin_headers)).json()
    silent = next(a for a in body["needs_you"] if a["key"] == "silent_devices")
    assert silent["count"] == 1
    assert silent["href"] == "/devices"
