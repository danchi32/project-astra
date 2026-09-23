"""Remote control: the record and the rules.

The three rules here were each paid for during the MeshCentral spike, and each one is a
place where the obvious implementation is wrong:

  * silence is not refusal (the engine reports both as "local user rejected")
  * one session per device (two prompts teach people to click Allow reflexively)
  * a reason is required (a prompt that can't say why stops being read)

Nothing in this module talks to a remote-control engine yet, so nothing here mocks one.
"""
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.security import hash_opaque_token
from app.models import AuditLog, Device, RemoteSession, RemoteSessionStatus, User, UserRole
from app.models.base import as_utc, utcnow
from app.services.entitlements import REMOTE_CONTROL
from app.services.exceptions import ConflictError, NotFoundError
from app.services.remote_control import (
    CONSENT_TIMEOUT,
    VIEWER_TIMEOUT,
    RemoteControlError,
    RemoteControlService,
    SessionAlreadyOpenError,
)

REASON = "Outlook keeps crashing and the restart didn't help"


async def _device(session_factory, org, machine="rc-1") -> uuid.UUID:
    async with session_factory() as s:
        device = Device(
            org_id=org.id, hostname="RC-PC", machine_id=machine,
            os_version="Windows 11", agent_version="0.6.4",
            token_hash=hash_opaque_token(f"tok-{machine}"), last_seen_at=utcnow(),
            # A device that can actually be requested has reported its relay node id in — a
            # request is refused without one (see the guard in remote_control.request). These
            # tests exercise the flow past that point, so the fixture stands for a ready device.
            meshcentral_node_id=f"node//{machine}",
        )
        s.add(device)
        await s.commit()
        return device.id


async def _grant(session_factory, org):
    """Turn the feature on for this org only — it is in no plan by design."""
    async with session_factory() as s:
        from app.models import Organization
        o = await s.get(Organization, org.id)
        o.entitlement_overrides = {REMOTE_CONTROL: True}
        await s.commit()


async def _actor(session_factory, user_id) -> User:
    async with session_factory() as s:
        return await s.get(User, user_id)


# ── Rule 1: silence is not refusal ────────────────────────────────────────


async def test_a_prompt_nobody_answers_becomes_no_response_not_declined(
    session_factory, org, admin_user
):
    """The regression this whole enum exists for.

    In the spike the tester clicked Allow, but slower than the engine's 30-second window.
    The engine reported "local user rejected" and the console showed a refusal that never
    happened. A technician acting on that would stop helping a customer who had said yes.
    """
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org)

    async with session_factory() as s:
        actor = await s.get(User, admin_user.id)
        rs = await RemoteControlService(s).request(
            actor=actor, device_id=device_id, reason=REASON)
        session_id = rs.id
        assert rs.status is RemoteSessionStatus.PENDING

    # Nobody answers, and the deadline passes.
    async with session_factory() as s:
        row = await s.get(RemoteSession, session_id)
        row.requested_at = utcnow() - CONSENT_TIMEOUT - timedelta(seconds=1)
        await s.commit()

    async with session_factory() as s:
        assert await RemoteControlService(s).expire_stale() == 1

    async with session_factory() as s:
        row = await s.get(RemoteSession, session_id)
        assert row.status is RemoteSessionStatus.NO_RESPONSE
        assert row.status is not RemoteSessionStatus.DECLINED
        # Nobody answered, so nothing was answered AT — responded_at stays empty.
        assert row.responded_at is None


async def test_a_prompt_still_inside_the_window_is_left_alone(
    session_factory, org, admin_user
):
    """The sweep must not retire a request the person is still looking at."""
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "rc-2")

    async with session_factory() as s:
        actor = await s.get(User, admin_user.id)
        rs = await RemoteControlService(s).request(
            actor=actor, device_id=device_id, reason=REASON)
        session_id = rs.id

    async with session_factory() as s:
        assert await RemoteControlService(s).expire_stale() == 0

    async with session_factory() as s:
        assert (await s.get(RemoteSession, session_id)).status is RemoteSessionStatus.PENDING


async def test_declined_is_reachable_only_by_an_actual_answer(
    session_factory, org, admin_user
):
    """DECLINED means a person said no. Nothing else may set it."""
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "rc-3")

    async with session_factory() as s:
        actor = await s.get(User, admin_user.id)
        rs = await RemoteControlService(s).request(
            actor=actor, device_id=device_id, reason=REASON)
        session_id = rs.id

    async with session_factory() as s:
        row = await RemoteControlService(s).record_response(
            session_id=session_id, accepted=False)
        assert row.status is RemoteSessionStatus.DECLINED
        assert row.responded_at is not None

    # And a refusal is recorded, because a technician who collects them is a pattern
    # somebody should be able to see.
    async with session_factory() as s:
        actions = (await s.execute(select(AuditLog.action))).scalars().all()
        assert "remote_session.decline" in actions


async def test_an_engine_failure_is_not_recorded_as_a_refusal(
    session_factory, org, admin_user
):
    """A relay that fell over says nothing about what the user wanted."""
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "rc-4")

    async with session_factory() as s:
        actor = await s.get(User, admin_user.id)
        session_id = (await RemoteControlService(s).request(
            actor=actor, device_id=device_id, reason=REASON)).id

    async with session_factory() as s:
        row = await RemoteControlService(s).fail(
            session_id=session_id, error="relay unreachable")
        assert row.status is RemoteSessionStatus.FAILED


async def test_an_approval_nobody_uses_expires_rather_than_staying_open(
    session_factory, org, admin_user
):
    """Consent is for a session that starts now, not one that starts whenever."""
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "rc-5")

    async with session_factory() as s:
        actor = await s.get(User, admin_user.id)
        session_id = (await RemoteControlService(s).request(
            actor=actor, device_id=device_id, reason=REASON)).id
    async with session_factory() as s:
        await RemoteControlService(s).record_response(session_id=session_id, accepted=True)

    async with session_factory() as s:
        row = await s.get(RemoteSession, session_id)
        row.responded_at = utcnow() - VIEWER_TIMEOUT - timedelta(seconds=1)
        await s.commit()

    async with session_factory() as s:
        assert await RemoteControlService(s).expire_stale() == 1
    async with session_factory() as s:
        assert (await s.get(RemoteSession, session_id)).status is RemoteSessionStatus.EXPIRED


# ── Rule 2: one session per device ────────────────────────────────────────


async def test_a_second_request_on_a_busy_device_is_refused(
    session_factory, org, admin_user
):
    """Two prompts on one screen is how people learn to click Allow without reading."""
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "rc-6")

    async with session_factory() as s:
        actor = await s.get(User, admin_user.id)
        first = await RemoteControlService(s).request(
            actor=actor, device_id=device_id, reason=REASON)

    async with session_factory() as s:
        actor = await s.get(User, admin_user.id)
        with pytest.raises(SessionAlreadyOpenError) as exc:
            await RemoteControlService(s).request(
                actor=actor, device_id=device_id, reason=REASON)
        # The caller is handed the session that IS open, so the portal can show it
        # instead of an error that invites a second click.
        assert exc.value.existing.id == first.id


async def test_a_finished_session_frees_the_device(session_factory, org, admin_user):
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "rc-7")

    async with session_factory() as s:
        actor = await s.get(User, admin_user.id)
        session_id = (await RemoteControlService(s).request(
            actor=actor, device_id=device_id, reason=REASON)).id
    async with session_factory() as s:
        await RemoteControlService(s).record_response(session_id=session_id, accepted=False)

    async with session_factory() as s:
        actor = await s.get(User, admin_user.id)
        again = await RemoteControlService(s).request(
            actor=actor, device_id=device_id, reason=REASON)
        assert again.status is RemoteSessionStatus.PENDING


# ── Rule 3: a reason, and who may ask ─────────────────────────────────────


@pytest.mark.parametrize("reason", ["", "   ", "fix", "help pls"])
async def test_a_request_without_a_real_reason_is_refused(
    session_factory, org, admin_user, reason
):
    """The person being asked reads this. A box nobody fills in is worse than no box."""
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, f"rc-r{len(reason)}")

    async with session_factory() as s:
        actor = await s.get(User, admin_user.id)
        with pytest.raises(RemoteControlError):
            await RemoteControlService(s).request(
                actor=actor, device_id=device_id, reason=reason)


async def test_a_regular_user_cannot_ask_for_someone_elses_screen(
    session_factory, org, regular_user
):
    """Requesting control of a colleague's machine is a different product."""
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "rc-8")

    async with session_factory() as s:
        actor = await s.get(User, regular_user.id)
        assert actor.role is UserRole.USER
        with pytest.raises(RemoteControlError):
            await RemoteControlService(s).request(
                actor=actor, device_id=device_id, reason=REASON)


async def test_a_device_in_another_org_is_not_found(
    session_factory, org, other_org, admin_user
):
    await _grant(session_factory, org)
    await _grant(session_factory, other_org)
    theirs = await _device(session_factory, other_org, "rc-9")

    async with session_factory() as s:
        actor = await s.get(User, admin_user.id)
        with pytest.raises(NotFoundError):
            await RemoteControlService(s).request(
                actor=actor, device_id=theirs, reason=REASON)


# ── The gate ──────────────────────────────────────────────────────────────


async def test_remote_control_is_expert_only(session_factory, org, admin_user):
    """Only the Expert plan carries it. An org below that cannot request a session at all,
    however online the device or willing the technician — the plan is the gate."""
    from app.models import Organization

    device_id = await _device(session_factory, org, "rc-10")

    async with session_factory() as s:
        o = await s.get(Organization, org.id)
        o.plan = "essential"
        await s.commit()

    async with session_factory() as s:
        actor = await s.get(User, admin_user.id)
        with pytest.raises(RemoteControlError, match="plan"):
            await RemoteControlService(s).request(
                actor=actor, device_id=device_id, reason=REASON)

    # Move the same org up to Expert and it is allowed — no override needed.
    async with session_factory() as s:
        o = await s.get(Organization, org.id)
        o.plan = "expert"
        await s.commit()

    async with session_factory() as s:
        actor = await s.get(User, admin_user.id)
        rs = await RemoteControlService(s).request(
            actor=actor, device_id=device_id, reason=REASON)
        assert rs.status is RemoteSessionStatus.PENDING


# ── The arc ───────────────────────────────────────────────────────────────


async def test_the_whole_arc_is_recorded(session_factory, org, admin_user):
    """Request, consent, connect, disconnect — with a duration at the end and an audit
    entry at every step. The duration is the number a customer asks about later."""
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "rc-11")

    async with session_factory() as s:
        actor = await s.get(User, admin_user.id)
        session_id = (await RemoteControlService(s).request(
            actor=actor, device_id=device_id, reason=REASON)).id

    async with session_factory() as s:
        await RemoteControlService(s).record_response(session_id=session_id, accepted=True)
    async with session_factory() as s:
        row = await RemoteControlService(s).mark_active(
            session_id=session_id, provider_session_id="mc-session-42")
        assert row.status is RemoteSessionStatus.ACTIVE

    # Backdate the start so the duration is a real number rather than zero.
    async with session_factory() as s:
        row = await s.get(RemoteSession, session_id)
        row.started_at = utcnow() - timedelta(seconds=90)
        await s.commit()

    async with session_factory() as s:
        actor = await s.get(User, admin_user.id)
        row = await RemoteControlService(s).end(session_id=session_id, actor=actor)
        assert row.status is RemoteSessionStatus.ENDED
        assert 85 <= row.duration_seconds <= 95

    async with session_factory() as s:
        actions = (await s.execute(select(AuditLog.action))).scalars().all()
        for step in ("remote_session.request", "remote_session.approve", "remote_session.end"):
            assert step in actions, (step, actions)


async def test_a_session_cannot_start_without_consent(session_factory, org, admin_user):
    """The gate that matters. An unanswered request must never become a live screen."""
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "rc-12")

    async with session_factory() as s:
        actor = await s.get(User, admin_user.id)
        session_id = (await RemoteControlService(s).request(
            actor=actor, device_id=device_id, reason=REASON)).id

    async with session_factory() as s:
        with pytest.raises(ConflictError):
            await RemoteControlService(s).mark_active(session_id=session_id)

    async with session_factory() as s:
        await RemoteControlService(s).record_response(session_id=session_id, accepted=False)
    async with session_factory() as s:
        with pytest.raises(ConflictError):
            await RemoteControlService(s).mark_active(session_id=session_id)


async def test_the_person_at_the_device_can_always_end_it(session_factory, org, admin_user):
    """Ended by the user, not the technician — and the audit log says which."""
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "rc-13")

    async with session_factory() as s:
        actor = await s.get(User, admin_user.id)
        session_id = (await RemoteControlService(s).request(
            actor=actor, device_id=device_id, reason=REASON)).id
    async with session_factory() as s:
        await RemoteControlService(s).record_response(session_id=session_id, accepted=True)
    async with session_factory() as s:
        await RemoteControlService(s).mark_active(session_id=session_id)

    async with session_factory() as s:
        row = await RemoteControlService(s).end(session_id=session_id, actor=None)
        assert row.status is RemoteSessionStatus.ENDED

    async with session_factory() as s:
        rows = (await s.execute(
            select(AuditLog.action, AuditLog.detail)
        )).all()
        end = next(d for a, d in rows if a == "remote_session.end")
        assert end["ended_by"] == "user"


# ── The AI must not be able to reach this ─────────────────────────────────


def test_no_ai_tool_exposes_remote_control():
    """Remote control is the purest `operator_only` case in CLAUDE.md: it interrupts a
    person rather than fixing a fault, and no telemetry can establish that someone should
    be watched. Enforced here rather than trusted to a prompt."""
    from app.services.ai.tools import _ACTION_IDS, TOOL_SCHEMAS

    names = {t["name"] for t in TOOL_SCHEMAS}
    assert not any("remote" in n.lower() for n in names), names
    assert not any("remote" in a.lower() for a in _ACTION_IDS), sorted(_ACTION_IDS)


async def test_both_sides_hanging_up_at_once_is_not_an_error(
    session_factory, org, admin_user
):
    """The user closes the banner as the technician clicks disconnect.

    That race is normal. Refusing the second call would show a failure to whoever lost it,
    and re-running the body would write a second audit entry and a second duration for one
    session — so `end` is idempotent and the first answer is the one that stands.
    """
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "rc-14")

    async with session_factory() as s:
        actor = await s.get(User, admin_user.id)
        session_id = (await RemoteControlService(s).request(
            actor=actor, device_id=device_id, reason=REASON)).id
    async with session_factory() as s:
        await RemoteControlService(s).record_response(session_id=session_id, accepted=True)
    async with session_factory() as s:
        await RemoteControlService(s).mark_active(session_id=session_id)

    async with session_factory() as s:
        first = await RemoteControlService(s).end(session_id=session_id, actor=None)
        first_ended_at, first_duration = first.ended_at, first.duration_seconds

    async with session_factory() as s:
        actor = await s.get(User, admin_user.id)
        second = await RemoteControlService(s).end(session_id=session_id, actor=actor)

    assert second.status is RemoteSessionStatus.ENDED
    # as_utc because SQLite hands back a naive datetime for a value that was written
    # tz-aware; the instant is what this assertion is about.
    assert as_utc(second.ended_at) == as_utc(first_ended_at)
    assert second.duration_seconds == first_duration

    async with session_factory() as s:
        ends = [a for a in (await s.execute(select(AuditLog.action))).scalars().all()
                if a == "remote_session.end"]
        assert len(ends) == 1, ends


async def test_a_late_failure_does_not_overwrite_a_refusal(
    session_factory, org, admin_user
):
    """Why the session ended is the useful part of the record. An engine error arriving
    after the person already said no must not rewrite that into a technical fault."""
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "rc-15")

    async with session_factory() as s:
        actor = await s.get(User, admin_user.id)
        session_id = (await RemoteControlService(s).request(
            actor=actor, device_id=device_id, reason=REASON)).id
    async with session_factory() as s:
        await RemoteControlService(s).record_response(session_id=session_id, accepted=False)

    async with session_factory() as s:
        row = await RemoteControlService(s).fail(
            session_id=session_id, error="relay timed out")
        assert row.status is RemoteSessionStatus.DECLINED
