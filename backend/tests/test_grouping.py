"""Device groups and user teams.

A group is a filter, and a filter that later drives bulk remediation. That is why the
membership checks matter more than they look: an id that slips into a group is an id that
later receives commands, and "which devices are in the Finance group" becomes "which
devices got the fix".

The other thing worth pinning down is what a team is NOT. Membership is not permission.
Nothing in the authorisation path reads these tables, and a test says so, because "add
them to the team" is the most natural-sounding way for that to stop being true.
"""
import pytest

from app.core.security import hash_opaque_token
from app.models import Device, UserRole
from app.schemas.grouping import GroupWrite
from app.services.exceptions import ConflictError, NotFoundError
from app.services.grouping import GroupingService
from app.services.sessions import SessionService
from app.services.telemetry import TelemetryService

from tests.test_sessions import _push, _session


async def _device(session, org_id, hostname):
    device = Device(
        org_id=org_id, hostname=hostname, machine_id=hostname.lower(),
        os_version="Windows 11", agent_version="0.8.0",
        token_hash=hash_opaque_token(hostname),
    )
    session.add(device)
    await session.flush()
    return device


# ── Device groups ─────────────────────────────────────────────────────────

async def test_create_list_and_count(session_factory, admin_user):
    async with session_factory() as session:
        service = GroupingService(session)
        group = await service.create_group(
            actor=admin_user,
            body=GroupWrite(name="Finance laptops", description="Ground floor", colour="#2563eb"),
        )
        assert group.device_count == 0

        d1 = await _device(session, admin_user.org_id, "FIN-LT-01")
        d2 = await _device(session, admin_user.org_id, "FIN-LT-02")
        await session.commit()
        await service.set_group_members(
            actor=admin_user, group_id=group.id, device_ids=[d1.id, d2.id]
        )
        listed = await service.list_groups(org_id=admin_user.org_id)

    assert [g.name for g in listed] == ["Finance laptops"]
    assert listed[0].device_count == 2


async def test_membership_is_replaced_not_merged(session_factory, admin_user):
    """The endpoint takes the whole set, because the operator is looking at a list of
    checkboxes and expects the boxes they unticked to be untick*ed*. A merge would make
    removing a device impossible through the only UI that exists for it."""
    async with session_factory() as session:
        service = GroupingService(session)
        group = await service.create_group(actor=admin_user, body=GroupWrite(name="HQ"))
        d1 = await _device(session, admin_user.org_id, "HQ-01")
        d2 = await _device(session, admin_user.org_id, "HQ-02")
        await session.commit()

        await service.set_group_members(actor=admin_user, group_id=group.id,
                                        device_ids=[d1.id, d2.id])
        await service.set_group_members(actor=admin_user, group_id=group.id,
                                        device_ids=[d2.id])
        members = await service.group_member_ids(org_id=admin_user.org_id, group_id=group.id)

    assert members == [d2.id]


async def test_a_device_can_be_in_several_groups(session_factory, admin_user):
    """The reason this is a new concept rather than an extension of Locations: a location is
    where a machine physically is, one value, and it cannot express "the finance laptops"
    (three floors) or "the 2019 refresh" (two sites) at the same time."""
    async with session_factory() as session:
        service = GroupingService(session)
        finance = await service.create_group(actor=admin_user, body=GroupWrite(name="Finance"))
        refresh = await service.create_group(actor=admin_user, body=GroupWrite(name="2019 refresh"))
        device = await _device(session, admin_user.org_id, "FIN-LT-09")
        await session.commit()

        await service.set_group_members(actor=admin_user, group_id=finance.id,
                                        device_ids=[device.id])
        await service.set_group_members(actor=admin_user, group_id=refresh.id,
                                        device_ids=[device.id])
        names = await service.groups_for_devices({device.id})

    assert sorted(names[device.id]) == ["2019 refresh", "Finance"]


async def test_a_device_from_another_org_cannot_be_added(
    session_factory, admin_user, other_org_user
):
    """A group drives bulk remediation later. An id smuggled in here is an id that receives
    commands then — so this is refused outright rather than silently dropped, which would
    also let a caller probe which ids exist elsewhere by watching the resulting count."""
    async with session_factory() as session:
        service = GroupingService(session)
        group = await service.create_group(actor=admin_user, body=GroupWrite(name="Ours"))
        theirs = await _device(session, other_org_user.org_id, "GLOBEX-01")
        await session.commit()

        with pytest.raises(NotFoundError):
            await service.set_group_members(
                actor=admin_user, group_id=group.id, device_ids=[theirs.id]
            )


async def test_another_orgs_group_is_not_found(session_factory, admin_user, other_org_user):
    async with session_factory() as session:
        service = GroupingService(session)
        theirs = await service.create_group(actor=other_org_user, body=GroupWrite(name="Theirs"))

        with pytest.raises(NotFoundError):
            await service.group_member_ids(org_id=admin_user.org_id, group_id=theirs.id)
        with pytest.raises(NotFoundError):
            await service.delete_group(actor=admin_user, group_id=theirs.id)


async def test_names_are_unique_within_an_org_but_not_across_them(
    session_factory, admin_user, other_org_user
):
    async with session_factory() as session:
        service = GroupingService(session)
        await service.create_group(actor=admin_user, body=GroupWrite(name="Finance"))
        with pytest.raises(ConflictError):
            await service.create_group(actor=admin_user, body=GroupWrite(name="finance"))
        # A different tenant naming their group the same thing is not a conflict.
        await service.create_group(actor=other_org_user, body=GroupWrite(name="Finance"))


async def test_deleting_a_group_leaves_the_devices_alone(session_factory, admin_user):
    """Worth a test because the opposite is a plausible reading of "delete the Finance
    laptops group", and it is the reading that would end a fleet."""
    async with session_factory() as session:
        service = GroupingService(session)
        group = await service.create_group(actor=admin_user, body=GroupWrite(name="Doomed"))
        device = await _device(session, admin_user.org_id, "KEEP-ME")
        await session.commit()
        await service.set_group_members(actor=admin_user, group_id=group.id,
                                        device_ids=[device.id])

        await service.delete_group(actor=admin_user, group_id=group.id)
        still_there = await session.get(Device, device.id)

    assert still_there is not None
    assert still_there.hostname == "KEEP-ME"


async def test_a_group_filters_the_sessions_view(session_factory, admin_user):
    """The point of groups, from the operator's side: 2,000 sessions is not a list anyone
    reads, and "the finance laptops" is."""
    async with session_factory() as session:
        service = GroupingService(session)
        group = await service.create_group(actor=admin_user, body=GroupWrite(name="Finance"))
        inside = await _device(session, admin_user.org_id, "FIN-LT-01")
        outside = await _device(session, admin_user.org_id, "OPS-LT-01")
        await session.commit()
        await service.set_group_members(actor=admin_user, group_id=group.id,
                                        device_ids=[inside.id])

        telemetry = TelemetryService(session)
        await telemetry.ingest(device=inside, data=_push([_session(2, "ACME\\olivia")]))
        await telemetry.ingest(device=outside, data=_push([_session(2, "ACME\\liam")]))

        page = await SessionService(session).list_page(actor=admin_user, group_id=group.id)

    assert page.total == 1
    assert page.items[0].hostname == "FIN-LT-01"
    assert page.items[0].groups == ["Finance"]


async def test_a_device_in_two_groups_appears_once(session_factory, admin_user):
    """Filtering by group is an EXISTS, not a join. A join would multiply a device's session
    rows by the number of groups it is in, and the page would show the same person twice."""
    async with session_factory() as session:
        service = GroupingService(session)
        a = await service.create_group(actor=admin_user, body=GroupWrite(name="A"))
        b = await service.create_group(actor=admin_user, body=GroupWrite(name="B"))
        device = await _device(session, admin_user.org_id, "BOTH-01")
        await session.commit()
        await service.set_group_members(actor=admin_user, group_id=a.id, device_ids=[device.id])
        await service.set_group_members(actor=admin_user, group_id=b.id, device_ids=[device.id])

        await TelemetryService(session).ingest(device=device, data=_push([_session()]))
        page = await SessionService(session).list_page(actor=admin_user, group_id=a.id)

    assert page.total == 1
    assert page.counts.all == 1


# ── User teams ────────────────────────────────────────────────────────────

async def test_teams_group_people(session_factory, admin_user, org):
    from tests.conftest import _create_user
    tech = await _create_user(session_factory, org.id, "t1@acme.com", "TechPass123!",
                              UserRole.TECHNICIAN)
    async with session_factory() as session:
        service = GroupingService(session)
        team = await service.create_team(actor=admin_user, body=GroupWrite(name="Service desk"))
        await service.set_team_members(actor=admin_user, team_id=team.id,
                                       user_ids=[admin_user.id, tech.id])
        listed = await service.list_teams(org_id=admin_user.org_id)

    assert listed[0].member_count == 2


async def test_team_membership_is_not_permission(session_factory, admin_user, regular_user):
    """The most natural-sounding way for authorisation to quietly break: someone decides that
    being in the on-call team should imply being able to act. RBAC reads `users.role` and
    nothing else — putting a plain user in a team must not move them an inch."""
    async with session_factory() as session:
        service = GroupingService(session)
        team = await service.create_team(actor=admin_user, body=GroupWrite(name="On call"))
        await service.set_team_members(actor=admin_user, team_id=team.id,
                                       user_ids=[regular_user.id])
        refreshed = await session.get(type(regular_user), regular_user.id)

    assert refreshed.role is UserRole.USER


async def test_a_user_from_another_org_cannot_join_a_team(
    session_factory, admin_user, other_org_user
):
    async with session_factory() as session:
        service = GroupingService(session)
        team = await service.create_team(actor=admin_user, body=GroupWrite(name="Ours"))
        with pytest.raises(NotFoundError):
            await service.set_team_members(
                actor=admin_user, team_id=team.id, user_ids=[other_org_user.id]
            )


# ── HTTP surface ──────────────────────────────────────────────────────────

async def test_a_plain_user_can_read_groups_but_not_change_them(client, user_headers):
    """The list is a filter dropdown on pages they already have; hiding the NAMES while
    showing the contents would be theatre. Changing them is staff work."""
    assert (await client.get("/api/v1/grouping/groups", headers=user_headers)).status_code == 200
    created = await client.post(
        "/api/v1/grouping/groups", headers=user_headers, json={"name": "Mine"}
    )
    assert created.status_code == 403


async def test_a_colour_that_is_not_a_colour_is_refused(client, admin_headers):
    """This value goes straight into a style attribute in the portal. A string that is not a
    colour is the beginning of a CSS injection, and there is no reason to accept one."""
    response = await client.post(
        "/api/v1/grouping/groups", headers=admin_headers,
        json={"name": "Bad", "colour": "red; background:url(x)"},
    )
    assert response.status_code == 422


# ── Bulk actions on a group ───────────────────────────────────────────────

async def _set_plan(session_factory, org_id, plan):
    """Group bulk actions are gated on the Expert plan, like the fleet-wide push.

    The plan has to be set EXPLICITLY to test the gate at all: normalise_plan answers EXPERT
    for an org whose plan is unset, so the fixture org gets every feature by default and a
    naive test of the refusal would pass for the wrong reason."""
    from sqlalchemy import select
    from app.models import Organization
    async with session_factory() as session:
        org = (await session.execute(
            select(Organization).where(Organization.id == org_id))).scalar_one()
        org.plan = plan
        await session.commit()


async def test_a_device_action_fans_out_over_every_device(session_factory, admin_user):
    async with session_factory() as session:
        service = GroupingService(session)
        group = await service.create_group(actor=admin_user, body=GroupWrite(name="HQ"))
        ids = []
        for host in ("HQ-01", "HQ-02", "HQ-03"):
            ids.append((await _device(session, admin_user.org_id, host)).id)
        await session.commit()
        await service.set_group_members(actor=admin_user, group_id=group.id, device_ids=ids)

        result = await service.run_group_action(
            actor=admin_user, group_id=group.id, action_id="flush_dns")

    assert result.fanned_over == "devices"
    assert result.targets == 3
    assert result.queued == 3
    assert result.failed == 0


async def test_a_session_action_fans_out_over_sessions_not_devices(session_factory, admin_user):
    """The distinction that matters. A terminal server with three people signed in is three
    sign-outs; treating it as one device would sign out whichever session the agent picked."""
    async with session_factory() as session:
        service = GroupingService(session)
        group = await service.create_group(actor=admin_user, body=GroupWrite(name="Servers"))
        server = await _device(session, admin_user.org_id, "SRV-01")
        laptop = await _device(session, admin_user.org_id, "LT-01")
        await session.commit()
        await service.set_group_members(
            actor=admin_user, group_id=group.id, device_ids=[server.id, laptop.id])

        telemetry = TelemetryService(session)
        await telemetry.ingest(device=server, data=_push([
            _session(2, "ACME\\emma"), _session(3, "ACME\\mason"), _session(4, "ACME\\ava"),
        ]))
        await telemetry.ingest(device=laptop, data=_push([_session(1, "ACME\\liam")]))

        result = await service.run_group_action(
            actor=admin_user, group_id=group.id, action_id="lock_session")

    assert result.fanned_over == "sessions"
    # Four sessions across two devices — not two.
    assert result.targets == 4
    assert result.queued == 4


async def test_a_session_with_nobody_signed_in_is_skipped(session_factory, admin_user):
    """A machine at its logon screen. Locking an empty desktop is a no-op that would still
    spend a task, an audit line and a round trip to the device."""
    async with session_factory() as session:
        service = GroupingService(session)
        group = await service.create_group(actor=admin_user, body=GroupWrite(name="Floor"))
        device = await _device(session, admin_user.org_id, "FLOOR-01")
        await session.commit()
        await service.set_group_members(
            actor=admin_user, group_id=group.id, device_ids=[device.id])
        await TelemetryService(session).ingest(device=device, data=_push([
            _session(1, None), _session(2, "ACME\\olivia"),
        ]))

        result = await service.run_group_action(
            actor=admin_user, group_id=group.id, action_id="lock_session")

    assert result.targets == 1
    assert result.queued == 1


async def test_an_empty_group_does_nothing_rather_than_erroring(session_factory, admin_user):
    async with session_factory() as session:
        service = GroupingService(session)
        group = await service.create_group(actor=admin_user, body=GroupWrite(name="Empty"))
        result = await service.run_group_action(
            actor=admin_user, group_id=group.id, action_id="flush_dns")

    assert result.targets == 0
    assert result.queued == 0
    assert result.failed == 0


async def test_tiers_are_still_enforced_per_device(session_factory, org, admin_user):
    """The point of reusing the single-device path. A technician pushing an admin-only action
    at a group of machines gets refusals, not sign-outs — and the counts say so rather than
    the batch silently succeeding."""
    from tests.conftest import _create_user
    technician = await _create_user(
        session_factory, org.id, "bulktech@acme.com", "TechPass123!", UserRole.TECHNICIAN)
    async with session_factory() as session:
        service = GroupingService(session)
        group = await service.create_group(actor=admin_user, body=GroupWrite(name="Tiered"))
        ids = [(await _device(session, admin_user.org_id, h)).id for h in ("T-01", "T-02")]
        await session.commit()
        await service.set_group_members(actor=admin_user, group_id=group.id, device_ids=ids)

        result = await service.run_group_action(
            actor=technician, group_id=group.id, action_id="block_usb_storage")

    assert result.queued == 0
    assert result.failed == 2


async def test_a_bulk_push_is_audited_at_the_group_level(session_factory, admin_user):
    """Per-task records say what happened to each machine. This one answers the question
    actually asked after a bad push: who aimed what at which group, and how big was it."""
    from sqlalchemy import select
    from app.models import AuditLog
    async with session_factory() as session:
        service = GroupingService(session)
        group = await service.create_group(actor=admin_user, body=GroupWrite(name="Audited"))
        device = await _device(session, admin_user.org_id, "AUD-01")
        await session.commit()
        await service.set_group_members(
            actor=admin_user, group_id=group.id, device_ids=[device.id])
        await service.run_group_action(
            actor=admin_user, group_id=group.id, action_id="flush_dns")

        entry = (await session.execute(
            select(AuditLog).where(AuditLog.action == "device_group.bulk_action")
        )).scalars().first()

    assert entry is not None
    assert entry.detail["action_id"] == "flush_dns"
    assert entry.detail["name"] == "Audited"
    assert entry.detail["queued"] == 1


async def test_group_bulk_is_expert_only(client, admin_headers, admin_user, session_factory):
    """Same gating as the fleet-wide push: it is the same capability with a nicer target
    selector. 402 rather than 403 — the role is fine, the plan is not."""
    async with session_factory() as session:
        group = await GroupingService(session).create_group(
            actor=admin_user, body=GroupWrite(name="Gated"))
        group_id = str(group.id)

    await _set_plan(session_factory, admin_user.org_id, "essential")
    denied = await client.post(f"/api/v1/grouping/groups/{group_id}/actions",
                               headers=admin_headers, json={"action_id": "flush_dns"})
    assert denied.status_code == 402

    await _set_plan(session_factory, admin_user.org_id, "expert")
    allowed = await client.post(f"/api/v1/grouping/groups/{group_id}/actions",
                                headers=admin_headers, json={"action_id": "flush_dns"})
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["fanned_over"] == "devices"
