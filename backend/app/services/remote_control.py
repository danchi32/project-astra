"""Remote control: the rules around taking over someone's screen.

This module owns the RECORD and the RULES. It does not talk to the remote-control engine —
that lands with the engine itself, and an endpoint that cannot reach a device would be a
lie dressed as a feature. What is here is the part worth settling first, because it is the
part the spike proved is easy to get wrong.

Three rules, each one paid for:

1. Silence is not refusal. A prompt that times out becomes NO_RESPONSE, never DECLINED.
   The engine reports both as "local user rejected"; during the spike that told a
   technician their customer had refused a session the customer never saw. `expire_stale`
   is what makes the distinction real rather than documented.

2. One session per device. A second prompt arriving while the first is on screen teaches
   people to click Allow to make dialogs go away, which is how consent stops meaning
   anything.

3. A reason is required, and the person being asked reads it. A prompt that cannot say why
   is a prompt people learn to click through.

Not reachable by the AI, ever. This is the purest case of `operator_only` in CLAUDE.md —
an action that interrupts a person rather than fixing a fault. No telemetry can establish
that someone should be watched, so no tool exposes this to the reasoning engine.
"""
from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    OPEN_STATUSES,
    Device,
    Organization,
    RemoteSession,
    RemoteSessionStatus,
    User,
    UserRole,
)
from app.models.base import as_utc, utcnow
from app.repositories.remote_sessions import RemoteSessionRepository
from app.services.audit import AuditService
from app.services.entitlements import REMOTE_CONTROL, features_for
from app.services.exceptions import ConflictError, NotFoundError, ServiceError

#: How long the person at the keyboard has to answer before the request lapses.
#:
#: The engine's own default is 30 seconds and that is too short — it is roughly the time it
#: takes to notice a prompt behind a full-screen window, which is why the spike produced a
#: refusal nobody made. Long enough to walk back to the desk; short enough that a
#: technician is not left watching a spinner.
CONSENT_TIMEOUT = timedelta(seconds=120)

#: How long an approved session waits for the technician to actually open the viewer.
#: Consent is for a session that starts now, not for one that starts whenever somebody
#: gets round to it.
VIEWER_TIMEOUT = timedelta(seconds=120)

#: A reason short enough to be meaningless is worse than no box at all: it trains the
#: person answering to stop reading the prompt.
MIN_REASON_LENGTH = 10

#: Who may ask for someone's screen. Never UserRole.USER — a person requesting control of
#: a colleague's machine is a different product with a different consent story.
REQUESTER_ROLES = frozenset({UserRole.ADMIN, UserRole.TECHNICIAN})


class RemoteControlError(ServiceError):
    pass


class SessionAlreadyOpenError(RemoteControlError):
    """A session is already in flight on this device.

    Its own type because it is not a failure — the thing the caller wants is already
    happening, and the API answers 409 so the portal can say so rather than inviting a
    second click that would put a second prompt on the same screen.
    """

    def __init__(self, message: str, existing: RemoteSession) -> None:
        super().__init__(message)
        self.existing = existing


class RemoteControlService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = RemoteSessionRepository(session)
        self.audit = AuditService(session)

    # -- Requesting -----------------------------------------------------------

    async def request(
        self, *, actor: User, device_id: uuid.UUID, reason: str
    ) -> RemoteSession:
        """Ask the person at `device_id` for control of their screen.

        Returns a PENDING session. Nothing is connected yet and nothing will be until they
        answer; if they never do, `expire_stale` turns this into NO_RESPONSE.
        """
        if actor.role not in REQUESTER_ROLES:
            raise RemoteControlError(
                "Only an administrator or technician can request remote control."
            )

        reason = (reason or "").strip()
        if len(reason) < MIN_REASON_LENGTH:
            raise RemoteControlError(
                "Say why you need to connect — the person being asked reads this, "
                f"and it needs at least {MIN_REASON_LENGTH} characters."
            )

        if not await self._org_has(actor.org_id, REMOTE_CONTROL):
            raise RemoteControlError("This organization's plan doesn't include remote control.")

        device = await self.session.get(Device, device_id)
        if device is None or device.org_id != actor.org_id:
            raise NotFoundError("Device not found")

        # No relay identity means the remote-support agent has not installed on this device
        # yet, so there is nothing on it to receive the request or raise the prompt. Refusing
        # here — rather than opening a session that can never mint a viewer link — is the
        # difference between "this device isn't set up for remote support yet" and a spinner
        # that counts down to nothing. (Commonly the endpoint's own security policy is
        # blocking the agent from installing; the message stays about the visible symptom.)
        if not device.meshcentral_node_id:
            raise RemoteControlError(
                "Remote support isn't ready on this device yet — its support agent hasn't "
                "finished setting up. Once the device reports it in, this will work."
            )

        existing = await self.repo.open_for_device(device_id)
        if existing is not None:
            raise SessionAlreadyOpenError(
                "A remote session is already open on this device.", existing
            )

        now = utcnow()
        remote_session = await self.repo.add(
            RemoteSession(
                org_id=actor.org_id,
                device_id=device_id,
                requested_by_user_id=actor.id,
                reason=reason,
                status=RemoteSessionStatus.PENDING,
                requested_at=now,
            )
        )
        await self.audit.record(
            org_id=actor.org_id,
            actor_id=actor.id,
            action="remote_session.request",
            target_type="device",
            target_id=str(device_id),
            detail={"session_id": str(remote_session.id), "reason": reason},
        )
        await self.session.commit()
        return remote_session

    # -- The answer -----------------------------------------------------------

    async def record_response(
        self, *, session_id: uuid.UUID, accepted: bool
    ) -> RemoteSession:
        """The person answered. This is the only path to DECLINED.

        Nothing else in this module may set DECLINED — a timeout is NO_RESPONSE, and a
        failure is FAILED. Keeping the one status that means "a human said no" reachable
        from exactly one place is what stops the distinction eroding later.
        """
        remote_session = await self._get(session_id)
        if remote_session.status is not RemoteSessionStatus.PENDING:
            raise ConflictError("This session is no longer waiting for an answer.")

        remote_session.status = (
            RemoteSessionStatus.APPROVED if accepted else RemoteSessionStatus.DECLINED
        )
        remote_session.responded_at = utcnow()

        await self.audit.record(
            org_id=remote_session.org_id,
            actor_id=None,          # the person at the device, who has no portal account
            action="remote_session.approve" if accepted else "remote_session.decline",
            target_type="remote_session",
            target_id=str(remote_session.id),
            detail={"device_id": str(remote_session.device_id)},
        )
        await self.session.commit()
        return remote_session

    async def mark_active(
        self, *, session_id: uuid.UUID, provider_session_id: str | None = None
    ) -> RemoteSession:
        """Pixels are flowing. Only an APPROVED session may start."""
        remote_session = await self._get(session_id)
        if remote_session.status is not RemoteSessionStatus.APPROVED:
            raise ConflictError("Only an approved session can start.")

        remote_session.status = RemoteSessionStatus.ACTIVE
        remote_session.started_at = utcnow()
        if provider_session_id:
            remote_session.provider_session_id = provider_session_id
        await self.session.commit()
        return remote_session

    async def end(
        self, *, session_id: uuid.UUID, actor: User | None = None
    ) -> RemoteSession:
        """Finish a session. Either side may do this, and the user's side always can.

        `actor` is None when the person at the device ended it, which is the case worth
        being able to read back out of the audit log later.

        Idempotent, deliberately. Both sides can hang up at the same moment — the user
        closes the banner as the technician clicks disconnect — and that race is normal,
        not an error. Refusing the second call would put a failure in front of whoever lost
        it, and re-running the body would write a second audit entry and a second duration
        for one session.
        """
        remote_session = await self._get(session_id)
        if actor is not None and remote_session.org_id != actor.org_id:
            raise NotFoundError("Remote session not found")
        if remote_session.status not in OPEN_STATUSES:
            return remote_session

        now = utcnow()
        remote_session.status = RemoteSessionStatus.ENDED
        remote_session.ended_at = now
        if remote_session.started_at is not None:
            remote_session.duration_seconds = int(
                (now - as_utc(remote_session.started_at)).total_seconds()
            )

        await self.audit.record(
            org_id=remote_session.org_id,
            actor_id=actor.id if actor else None,
            action="remote_session.end",
            target_type="remote_session",
            target_id=str(remote_session.id),
            detail={
                "device_id": str(remote_session.device_id),
                "duration_seconds": remote_session.duration_seconds,
                "ended_by": "technician" if actor else "user",
            },
        )
        await self.session.commit()
        return remote_session

    async def fail(self, *, session_id: uuid.UUID, error: str) -> RemoteSession:
        """The engine could not start the session. Not the user's doing, so not DECLINED."""
        remote_session = await self._get(session_id)
        if remote_session.status not in OPEN_STATUSES:
            # A failure arriving after the session already finished changes nothing, and
            # must not overwrite a decline — the reason it ended is the useful part.
            return remote_session
        remote_session.status = RemoteSessionStatus.FAILED
        remote_session.ended_at = utcnow()
        await self.audit.record(
            org_id=remote_session.org_id,
            actor_id=None,
            action="remote_session.fail",
            target_type="remote_session",
            target_id=str(remote_session.id),
            detail={"error": error[:500]},
        )
        await self.session.commit()
        return remote_session

    # -- The sweep ------------------------------------------------------------

    async def expire_stale(self) -> int:
        """Retire requests nobody answered, and approvals nobody used.

        This is where NO_RESPONSE comes from, and the reason it is a sweep rather than a
        timer: the answer has to arrive even when the technician has closed the portal and
        the device has gone offline. Both are the common case for a prompt nobody saw.

        Returns how many sessions were moved, so a caller can log it.
        """
        now = utcnow()
        result = await self.session.execute(
            select(RemoteSession).where(
                RemoteSession.status.in_(
                    [RemoteSessionStatus.PENDING, RemoteSessionStatus.APPROVED]
                )
            )
        )
        moved = 0
        for remote_session in result.scalars().all():
            if remote_session.status is RemoteSessionStatus.PENDING:
                deadline = as_utc(remote_session.requested_at) + CONSENT_TIMEOUT
                new_status = RemoteSessionStatus.NO_RESPONSE
            else:
                responded = remote_session.responded_at or remote_session.requested_at
                deadline = as_utc(responded) + VIEWER_TIMEOUT
                new_status = RemoteSessionStatus.EXPIRED

            if now < deadline:
                continue

            remote_session.status = new_status
            remote_session.ended_at = now
            await self.audit.record(
                org_id=remote_session.org_id,
                actor_id=None,
                action=f"remote_session.{new_status.value}",
                target_type="remote_session",
                target_id=str(remote_session.id),
                detail={"device_id": str(remote_session.device_id)},
            )
            moved += 1

        if moved:
            await self.session.commit()
        return moved

    # -- Reading --------------------------------------------------------------

    async def get(self, *, actor: User, session_id: uuid.UUID) -> RemoteSession:
        remote_session = await self.repo.get(session_id)
        if remote_session is None or remote_session.org_id != actor.org_id:
            raise NotFoundError("Remote session not found")
        return remote_session

    async def list_page(
        self,
        *,
        actor: User,
        device_id: uuid.UUID | None = None,
        status: list[RemoteSessionStatus] | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[RemoteSession], int]:
        return await self.repo.list_page(
            actor.org_id, device_id=device_id, status=status, offset=offset, limit=limit
        )

    # -- Internals ------------------------------------------------------------

    async def _get(self, session_id: uuid.UUID) -> RemoteSession:
        remote_session = await self.repo.get(session_id)
        if remote_session is None:
            raise NotFoundError("Remote session not found")
        return remote_session

    async def _org_has(self, org_id: uuid.UUID, feature: str) -> bool:
        org = await self.session.get(Organization, org_id)
        if org is None:
            # Matches RemediationService: a lookup miss must not switch a customer's
            # product off. The entitlement dependency on the route is the real gate.
            return True
        return feature in features_for(org.plan, org.entitlement_overrides)
