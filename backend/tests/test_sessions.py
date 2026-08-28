"""Logon sessions: what gets stored, what gets shown, and who may act on one.

Three concerns, and they fail in different ways, so they are tested separately:

  * INGEST — sessions ride on the 60-second telemetry push, so the fingerprint that skips
    an unchanged rewrite is the difference between "a few writes a day" and "every session
    row of every device, every minute". A regression there is invisible until the database
    is on fire.
  * READING — the counts above the table and the rows in it have to agree, and both have to
    stop at the organization's own boundary.
  * ACTING — every session action interrupts a person, so the tier is the whole point.
"""
import uuid

import pytest

from app.core.security import hash_opaque_token
from app.models import Device, DeviceSession, RemediationStatus, UserRole
from app.models.base import utcnow
from app.schemas.telemetry import TelemetryPush
from app.services.remediation.service import RemediationError
from app.services.sessions import SessionService
from app.services.telemetry import TelemetryService


def _push(sessions, **overrides) -> TelemetryPush:
    return TelemetryPush(
        collected_at=utcnow(),
        cpu_percent=5.0, ram_total_mb=16384, ram_used_mb=8192,
        disks=[{"drive": "C:", "total_gb": 500, "used_gb": 200, "free_gb": 300}],
        sessions=sessions,
        **overrides,
    )


def _session(session_id=2, username="ACME\\olivia", state="active", connection="console",
             **extra) -> dict:
    return {
        "session_id": session_id, "username": username, "state": state,
        "connection": connection, "station": extra.pop("station", "Console"),
        "client_name": extra.pop("client_name", None),
        "logon_at": extra.pop("logon_at", None),
        "idle_seconds": extra.pop("idle_seconds", None),
    }


async def _device(session, org_id, hostname="SESS-PC", last_seen=None):
    device = Device(
        org_id=org_id, hostname=hostname, machine_id=hostname.lower(),
        os_version="Windows 11", agent_version="0.8.0",
        token_hash=hash_opaque_token(hostname),
        last_seen_at=last_seen or utcnow(),
    )
    session.add(device)
    await session.flush()
    return device


async def _count_rows(session, device_id) -> int:
    from sqlalchemy import func, select
    return int((await session.execute(
        select(func.count()).select_from(DeviceSession)
        .where(DeviceSession.device_id == device_id)
    )).scalar_one())


# ── Ingest ────────────────────────────────────────────────────────────────

async def test_sessions_are_stored_from_the_telemetry_push(session_factory, admin_user):
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id)
        await TelemetryService(session).ingest(
            device=device,
            data=_push([_session(2, "ACME\\olivia"), _session(3, "ACME\\liam", connection="rdp",
                                                              station="RDP-Tcp#3", client_name="LAPTOP-7")]),
        )
        rows = await SessionService(session).for_device(actor=admin_user, device_id=device.id)

    assert {r.session_id for r in rows} == {2, 3}
    rdp = next(r for r in rows if r.session_id == 3)
    assert rdp.connection == "rdp"
    assert rdp.client_name == "LAPTOP-7"


async def test_an_unchanged_session_set_is_not_rewritten(session_factory, admin_user):
    """The fingerprint, which is the only thing standing between this table and a rewrite of
    every row of every device every 60 seconds. `updated_at` is untouched when the write is
    skipped, so comparing row identity proves nothing was replaced."""
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id)
        service = TelemetryService(session)
        await service.ingest(device=device, data=_push([_session()]))
        first = (await SessionService(session).for_device(
            actor=admin_user, device_id=device.id))[0].id

        await service.ingest(device=device, data=_push([_session()]))
        second = (await SessionService(session).for_device(
            actor=admin_user, device_id=device.id))[0].id

    # A delete-then-insert would have produced a new row id.
    assert first == second


async def test_idle_time_alone_does_not_trigger_a_rewrite(session_factory, admin_user):
    """Idle seconds change on every single push by definition. Including them in the
    fingerprint would make it miss every time, which is the same as not having one."""
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id)
        service = TelemetryService(session)
        await service.ingest(device=device, data=_push([_session(idle_seconds=10)]))
        first = (await SessionService(session).for_device(
            actor=admin_user, device_id=device.id))[0].id
        await service.ingest(device=device, data=_push([_session(idle_seconds=900)]))
        second = (await SessionService(session).for_device(
            actor=admin_user, device_id=device.id))[0].id

    assert first == second


async def test_signing_out_clears_the_row(session_factory, admin_user):
    """An empty list is a real answer — "nobody is signed in" — and has to clear the table.
    If it were treated as "nothing reported", the portal would show the last person to use
    a machine as still being on it, indefinitely."""
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id)
        service = TelemetryService(session)
        await service.ingest(device=device, data=_push([_session()]))
        assert await _count_rows(session, device.id) == 1

        await service.ingest(device=device, data=_push([]))
        assert await _count_rows(session, device.id) == 0


async def test_an_agent_that_reports_nothing_leaves_the_rows_alone(session_factory, admin_user):
    """None is not []. An older agent that does not know about sessions sends null, and
    treating that as "nobody is signed in" would empty the Sessions page across a fleet the
    moment one machine lagged a release behind."""
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id)
        service = TelemetryService(session)
        await service.ingest(device=device, data=_push([_session()]))
        await service.ingest(device=device, data=_push(None))
        assert await _count_rows(session, device.id) == 1


async def test_an_unknown_session_state_is_rejected(session_factory):
    """The agent already narrowed Windows' nine connect-states to the two that mean a person
    has a desktop. Anything else arriving here means the two sides disagree about what a
    session is, and storing it would put a row on the page that nothing can render."""
    with pytest.raises(ValueError):
        _push([_session(state="shadowing")])


# ── Reading ───────────────────────────────────────────────────────────────

async def test_the_list_filters_and_counts_agree(session_factory, admin_user):
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id)
        await TelemetryService(session).ingest(device=device, data=_push([
            _session(2, "ACME\\olivia", state="active", connection="console"),
            _session(3, "ACME\\liam", state="disconnected", connection="rdp", station="RDP-Tcp#3"),
            _session(4, "ACME\\ava", state="active", connection="rdp", station="RDP-Tcp#4"),
        ]))
        service = SessionService(session)
        everything = await service.list_page(actor=admin_user)
        just_rdp = await service.list_page(actor=admin_user, connection="rdp")

    assert everything.total == 3
    assert everything.counts.active == 2
    assert everything.counts.disconnected == 1
    assert everything.counts.console == 1
    assert everything.counts.rdp == 2
    assert just_rdp.total == 2
    # The counts describe the whole filtered set, not the tab you are standing in — so
    # filtering to RDP must not make the tab strip claim there are no console sessions.
    assert just_rdp.counts.console == 1


async def test_search_matches_the_user_the_host_and_the_rdp_client(session_factory, admin_user):
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id, hostname="FIN-LT-01")
        await TelemetryService(session).ingest(device=device, data=_push([
            _session(2, "ACME\\olivia"),
            _session(3, "ACME\\liam", connection="rdp", station="RDP-Tcp#3", client_name="JUMPBOX-2"),
        ]))
        service = SessionService(session)
        assert (await service.list_page(actor=admin_user, q="olivia")).total == 1
        assert (await service.list_page(actor=admin_user, q="fin-lt")).total == 2
        assert (await service.list_page(actor=admin_user, q="jumpbox")).total == 1


async def test_one_org_never_sees_anothers_sessions(
    session_factory, admin_user, other_org_user
):
    async with session_factory() as session:
        theirs = await _device(session, other_org_user.org_id, hostname="GLOBEX-PC")
        await TelemetryService(session).ingest(device=theirs, data=_push([_session()]))
        page = await SessionService(session).list_page(actor=admin_user)

    assert page.total == 0
    assert page.counts.all == 0


async def test_a_stale_session_is_marked_as_such(session_factory, admin_user):
    """A session row on a device that stopped checking in hours ago is a record of who WAS
    there. Without the device's own freshness beside it the page presents it as who IS
    there, and a technician acts on a desk that has been empty since yesterday."""
    from datetime import timedelta
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id,
                               last_seen=utcnow() - timedelta(hours=13))
        await TelemetryService(session).ingest(device=device, data=_push([_session()]))
        rows = await SessionService(session).for_device(actor=admin_user, device_id=device.id)

    assert rows[0].device_online is False


# ── Acting ────────────────────────────────────────────────────────────────

async def test_locking_a_session_queues_an_approved_task(session_factory, admin_user):
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id)
        task = await SessionService(session).act(
            actor=admin_user, device_id=device.id, action_id="lock_session", session_id=2,
        )

    assert task.action_id == "lock_session"
    # The session id has to survive to the agent — without it the action means "whichever
    # session the agent felt like", which on a multi-user machine is a coin flip.
    assert task.params == {"session_id": "2"}
    assert task.status is RemediationStatus.APPROVED


async def test_signing_out_is_admin_only(session_factory, org, admin_user):
    """A technician can lock a screen and send a message. Signing someone out destroys
    unsaved work, so it needs an admin — and the refusal has to come from the tier check,
    not from the portal choosing not to draw the button."""
    from tests.conftest import _create_user
    technician = await _create_user(
        session_factory, org.id, "tech@acme.com", "TechPass123!", UserRole.TECHNICIAN
    )
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id)
        service = SessionService(session)
        # Allowed at this tier...
        await service.act(actor=technician, device_id=device.id,
                          action_id="lock_session", session_id=2)
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id, hostname="SESS-PC2")
        with pytest.raises(RemediationError, match="trust tier"):
            await SessionService(session).act(
                actor=technician, device_id=device.id,
                action_id="logoff_session", session_id=2,
            )


async def test_session_zero_is_refused(session_factory, admin_user):
    """Session 0 is where Windows services live. It has no desktop and nobody is signed into
    it, so an action aimed there does nothing while reporting that it worked."""
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id)
        with pytest.raises(RemediationError, match="services session"):
            await SessionService(session).act(
                actor=admin_user, device_id=device.id,
                action_id="lock_session", session_id=0,
            )


async def test_an_empty_message_is_refused(session_factory, admin_user):
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id)
        with pytest.raises(RemediationError, match="message is required"):
            await SessionService(session).act(
                actor=admin_user, device_id=device.id,
                action_id="message_session", session_id=2, message="   ",
            )


async def test_a_device_in_another_org_is_not_found(
    session_factory, admin_user, other_org_user
):
    async with session_factory() as session:
        theirs = await _device(session, other_org_user.org_id, hostname="GLOBEX-PC")
        from app.services.exceptions import NotFoundError
        with pytest.raises(NotFoundError):
            await SessionService(session).act(
                actor=admin_user, device_id=theirs.id,
                action_id="lock_session", session_id=2,
            )


async def test_only_session_actions_reach_this_path(session_factory, admin_user):
    """"restart_explorer with a session id" is a client bug, and reads as one — a 404 rather
    than a tier error, which would suggest the caller was merely unlucky with permissions."""
    from app.services.exceptions import NotFoundError
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id)
        with pytest.raises(NotFoundError):
            await SessionService(session).act(
                actor=admin_user, device_id=device.id,
                action_id="restart_explorer", session_id=2,
            )


async def test_the_assistant_cannot_lock_or_message_anyone():
    """These act on a PERSON, not a fault. No telemetry establishes that someone should be
    interrupted, and a message box the model can address is a phishing primitive for anything
    that gets text in front of it."""
    from app.services.ai.tools import TOOL_SCHEMAS
    schema = next(t for t in TOOL_SCHEMAS if t["name"] == "propose_remediation")
    offered = set(schema["input_schema"]["properties"]["action_id"]["enum"])
    assert "lock_session" not in offered
    assert "message_session" not in offered
    assert "logoff_session" not in offered       # admin-only as well
    assert "reset_local_password" not in offered


# ── HTTP surface ──────────────────────────────────────────────────────────

async def test_a_plain_user_cannot_enumerate_their_colleagues(client, user_headers):
    """This endpoint is the neatest way in the product to find out who is at which desk."""
    response = await client.get("/api/v1/sessions", headers=user_headers)
    assert response.status_code == 403


async def test_a_refused_action_is_a_400_with_the_reason(client, admin_headers, admin_user,
                                                         session_factory):
    """The service's refusals are worth reading — "session 0 is the Windows services
    session", "a message is required". Without the exception mapping on the endpoint they
    escape as a 500, and every one of them reaches the operator as "Internal Server Error",
    which tells them nothing and makes a correct refusal look like an outage.

    Found by calling the running endpoint. The service-level tests above all passed while
    this was broken, because they never went through HTTP."""
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id)
        await session.commit()
        device_id = str(device.id)

    refused = await client.post(
        "/api/v1/sessions/actions", headers=admin_headers,
        json={"device_id": device_id, "action_id": "logoff_session", "session_id": 0},
    )
    assert refused.status_code == 400
    assert "services session" in refused.json()["detail"]

    blank = await client.post(
        "/api/v1/sessions/actions", headers=admin_headers,
        json={"device_id": device_id, "action_id": "message_session",
              "session_id": 2, "message": "   "},
    )
    assert blank.status_code == 400
    assert "message is required" in blank.json()["detail"]


async def test_an_unknown_device_is_a_404(client, admin_headers):
    response = await client.post(
        "/api/v1/sessions/actions", headers=admin_headers,
        json={"device_id": str(uuid.uuid4()), "action_id": "lock_session", "session_id": 2},
    )
    assert response.status_code == 404


async def test_pushing_the_same_action_twice_is_a_409(client, admin_headers, admin_user,
                                                      session_factory):
    """A conflict, not an error: the lock the operator asked for is already on its way. A
    400 would read as "that didn't go through" and invite the second click that creates the
    duplicate this is protecting them from."""
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id, hostname="DUP-PC")
        await session.commit()
        device_id = str(device.id)

    body = {"device_id": device_id, "action_id": "lock_session", "session_id": 2}
    assert (await client.post("/api/v1/sessions/actions", headers=admin_headers,
                              json=body)).status_code == 200
    again = await client.post("/api/v1/sessions/actions", headers=admin_headers, json=body)
    assert again.status_code == 409


async def test_the_endpoint_returns_a_page_with_counts(client, admin_headers, admin_user,
                                                       session_factory):
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id)
        await TelemetryService(session).ingest(device=device, data=_push([_session()]))

    response = await client.get("/api/v1/sessions", headers=admin_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["counts"]["active"] == 1
    assert body["items"][0]["username"] == "ACME\\olivia"
