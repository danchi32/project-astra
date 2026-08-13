"""Blocking USB across the whole fleet in one call.

The two properties worth pinning: it targets every active device the org actually has —
loaded server-side, not taken from the caller — and it is admin-only, because it closes a
port on every machine at once and the ordinary per-device tier check would otherwise be the
only thing standing between a technician and a fleet-wide change.
"""
from app.core.security import hash_opaque_token
from app.models import Device, RemediationStatus, RemediationTask
from app.services.fleet import FleetService


async def _devices(session, org_id, n):
    for i in range(n):
        session.add(Device(
            org_id=org_id, hostname=f"F{i}", machine_id=f"f{i}",
            os_version="Windows 11", agent_version="0.8.1",
            token_hash=hash_opaque_token(f"F{i}"),
        ))
    await session.flush()


async def test_it_queues_a_block_for_every_active_device(session_factory, admin_user):
    async with session_factory() as session:
        await _devices(session, admin_user.org_id, 3)
        await session.commit()

    async with session_factory() as session:
        result = await FleetService(session).usb_on_all(actor=admin_user, block=True)
        assert result.queued == 3
        await session.commit()

    from sqlalchemy import select
    async with session_factory() as session:
        tasks = (await session.execute(
            select(RemediationTask).where(RemediationTask.action_id == "block_usb_storage")
        )).scalars().all()
        assert len(tasks) == 3
        # Admin approved inline, so they go straight to approved rather than sitting pending.
        assert all(t.status is RemediationStatus.APPROVED for t in tasks)


async def test_the_endpoint_is_admin_only(client, user_headers):
    """Closing a port on every machine at once is not a non-admin action. The per-device
    tier check inside create_task blocks a technician even through the bulk path; requiring
    admin at the endpoint refuses the batch up front rather than after it all fails."""
    resp = await client.post("/api/v1/fleet/usb/block", headers=user_headers)
    assert resp.status_code == 403, resp.text


async def test_a_bad_state_is_refused(client, admin_headers):
    resp = await client.post("/api/v1/fleet/usb/sideways", headers=admin_headers)
    assert resp.status_code == 404
