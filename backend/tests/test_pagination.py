"""Paging behaviour that the per-feature tests don't cover.

Every list endpoint used to return its whole table. Paging them is easy; paging them WRONG
is easy too, and quiet — a second page that repeats the first, or a lookup that only ever
searches page 1, both render a page that looks completely normal and is missing rows.
"""
import uuid

from app.core.security import hash_opaque_token
from app.models import Asset, AuditLog, Device, RemediationSource, RemediationTask
from app.models.base import utcnow


async def _seed_audit(session_factory, org_id, n):
    async with session_factory() as session:
        for i in range(n):
            session.add(AuditLog(
                org_id=org_id, actor_id=None, action=f"probe.{i:03d}",
                target_type="probe", target_id=None, detail=None,
            ))
        await session.commit()


async def test_pages_do_not_overlap_and_cover_everything(
    client, admin_headers, admin_user, session_factory
):
    """The failure this guards is silent: an off-by-one in the offset gives you a second
    page that looks fine and repeats a row, and nobody notices until an audit."""
    await _seed_audit(session_factory, admin_user.org_id, 25)

    seen: list[str] = []
    total = None
    for page in (1, 2, 3):
        body = (await client.get(
            f"/api/v1/audit-logs?page={page}&page_size=10", headers=admin_headers
        )).json()
        total = body["total"]
        seen.extend(row["id"] for row in body["items"])

    assert len(seen) == len(set(seen)), "the same row appeared on two pages"
    assert len(seen) == total, f"paging returned {len(seen)} of {total} rows"


async def test_page_size_is_capped(client, admin_headers):
    """An uncapped page_size is a way to ask the server to serialise the whole table, which
    is the thing paging exists to prevent."""
    body = (await client.get(
        "/api/v1/audit-logs?page_size=999999999", headers=admin_headers
    )).json()
    assert body["page_size"] <= 10_000


async def test_a_nonsense_page_number_does_not_error(client, admin_headers):
    """Page numbers come from the address bar. Clamped, not rejected: a 422 would break the
    screen for someone who did nothing worse than edit a URL."""
    body = (await client.get("/api/v1/audit-logs?page=0", headers=admin_headers)).json()
    assert body["page"] == 1


async def test_an_empty_list_still_reports_one_page(client, user_headers):
    """`pages: 0` renders as "Page 1 of 0" in the footer."""
    body = (await client.get("/api/v1/notifications", headers=user_headers)).json()
    assert body["total"] == 0
    assert body["pages"] == 1


# ── Scoped lookups ─────────────────────────────────────────────────────────
#
# These endpoints are also used to find ONE thing. Before paging, callers fetched the whole
# list and searched it in the browser; that search silently becomes "search page 1" unless
# the filtering happens in the database.


async def _device_with_asset(session_factory, org_id, hostname, machine):
    async with session_factory() as session:
        device = Device(
            org_id=org_id, hostname=hostname, machine_id=machine,
            os_version="Windows 11", agent_version="0.7.4",
            token_hash=hash_opaque_token(machine), last_seen_at=utcnow(),
        )
        session.add(device)
        await session.flush()
        session.add(Asset(
            org_id=org_id, name=f"{hostname} laptop", category="laptop",
            status="in_use", device_id=device.id,
        ))
        await session.commit()
        return device.id


async def test_an_asset_is_found_by_device_even_beyond_the_first_page(
    client, admin_headers, admin_user, session_factory
):
    """The device page asks for its own asset. Finding it must not depend on where that row
    happens to sort in the register."""
    ids = [
        await _device_with_asset(session_factory, admin_user.org_id, f"PG-{i}", f"pg-{i}")
        for i in range(60)
    ]
    target = ids[-1]   # created last, so it is not on page 1 of a newest-first list

    body = (await client.get(
        f"/api/v1/assets?device_id={target}", headers=admin_headers
    )).json()
    assert body["total"] == 1
    assert body["items"][0]["device_id"] == str(target)


async def test_device_tasks_are_filtered_in_the_database(
    client, admin_headers, admin_user, session_factory
):
    """A device's in-flight work drives whether the portal offers to run a fix. Filtering a
    page of the org's history client-side would report a busy device as idle, and the
    duplicate guard would look broken rather than protective."""
    quiet = await _device_with_asset(session_factory, admin_user.org_id, "QUIET", "quiet-m")
    busy = await _device_with_asset(session_factory, admin_user.org_id, "BUSY", "busy-m")

    async with session_factory() as session:
        # Plenty of unrelated tasks, so the one that matters is not on the first page.
        for i in range(60):
            session.add(RemediationTask(
                org_id=admin_user.org_id, device_id=quiet, action_id="flush_dns",
                tier="automatic", status="succeeded", reason=f"noise {i}",
                source=RemediationSource.USER,
            ))
        await session.flush()
        session.add(RemediationTask(
            org_id=admin_user.org_id, device_id=busy, action_id="clear_system_temp",
            tier="automatic", status="dispatched", reason="the one that matters",
            source=RemediationSource.USER,
        ))
        await session.commit()

    body = (await client.get(
        f"/api/v1/remediations?device_id={busy}", headers=admin_headers
    )).json()
    assert body["total"] == 1
    assert body["items"][0]["action_id"] == "clear_system_temp"


async def test_status_filter_accepts_several_values(client, admin_headers, admin_user, session_factory):
    """Self-Healing shows "awaiting approval" and "history" as separate tables, so it asks
    for each separately rather than splitting one page in the browser."""
    device = await _device_with_asset(session_factory, admin_user.org_id, "ST", "st-m")
    async with session_factory() as session:
        for status in ("pending_approval", "succeeded", "failed"):
            session.add(RemediationTask(
                org_id=admin_user.org_id, device_id=device, action_id="flush_dns",
                tier="automatic", status=status, reason=status,
                source=RemediationSource.USER,
            ))
        await session.commit()

    body = (await client.get(
        "/api/v1/remediations?status=succeeded&status=failed", headers=admin_headers
    )).json()
    assert body["total"] == 2
    assert {r["status"] for r in body["items"]} == {"succeeded", "failed"}
