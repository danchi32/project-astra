"""The one process that turns relay events into SAVIO's record of what happened.

Why a process of its own, and not a few lines inside the API:

The relay tells us how a session went by PUSHING an event down a connection it expects
somebody to be holding open. There is nothing to poll. So something must hold that
connection — and if every API instance held one, every instance would receive every
event and every instance would write it. The backend runs up to twenty instances, which
would mean twenty audit entries and twenty status changes for one person clicking Allow.

Deduplicating that afterwards is the tempting alternative and the wrong one: it is the
kind of correctness that looks right in a test and fails quietly in production, at the
moment an instance is being replaced. One listener, running once, is a smaller thing to
get right and a smaller thing to reason about at 2am.

Deploy as its own Cloud Run service with min-instances=1 and max-instances=1. It serves
no traffic; it holds a socket.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models import OPEN_STATUSES, Device, RemoteSession, RemoteSessionStatus
from app.services.exceptions import ConflictError, NotFoundError
from app.services.meshcentral import (
    MSG_DESKTOP_ENDED,
    MSG_DESKTOP_REFUSED,
    MSG_DESKTOP_STARTED,
    MeshCentralClient,
    MeshCentralNotConfigured,
    RelayEvent,
)
from app.services.remote_control import RemoteControlService

logger = logging.getLogger(__name__)

#: How long to wait before reconnecting after the relay connection drops. Short enough
#: that a restart of the relay costs seconds of blindness, long enough not to hammer it.
RECONNECT_DELAY = 5.0

#: How often to retire prompts nobody answered, while any session could still lapse. This is
#: what makes NO_RESPONSE real, so it runs here rather than being left to whoever remembers.
SWEEP_INTERVAL = 15.0

#: How long to wait between sweeps while NOTHING is open. A 15s sweep around the clock was a
#: query every 15s against a database that otherwise scales to zero, so it never slept. With
#: nothing open there is nothing to retire; a relay event wakes the sweep at once, and reads in
#: RemoteControlService retire a lapsed prompt themselves, so this is only a backstop.
IDLE_SWEEP_INTERVAL = 6 * 60 * 60.0


class RemoteControlListener:
    def __init__(
        self,
        session_factory: async_sessionmaker,
        client: MeshCentralClient | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.client = client or MeshCentralClient()
        # Set by a relay event so an idling sweep runs now rather than hours from now.
        self._wake = asyncio.Event()

    # -- Mapping an event onto a session --------------------------------------

    async def handle(self, event: RelayEvent) -> bool:
        """Apply one relay event. Returns whether it changed anything.

        An event that matches no open session is dropped, deliberately and quietly. The
        common case is a refusal arriving after SAVIO's own sweep already recorded
        NO_RESPONSE — which is the whole point of the sweep running first, and not
        something to log as a problem.
        """
        if event.msgid not in (
            MSG_DESKTOP_STARTED, MSG_DESKTOP_ENDED, MSG_DESKTOP_REFUSED
        ):
            return False
        self._wake.set()
        if not event.node_id:
            return False

        async with self.session_factory() as session:
            remote_session = await self._open_session_for_node(session, event.node_id)
            if remote_session is None:
                return False

            service = RemoteControlService(session)
            try:
                if event.msgid == MSG_DESKTOP_REFUSED:
                    # Only reachable while ASTRA still thinks the prompt is live. Past
                    # its own consent window the session is already NO_RESPONSE and
                    # `_open_session_for_node` will not have returned it.
                    await service.record_response(
                        session_id=remote_session.id, accepted=False
                    )
                elif event.msgid == MSG_DESKTOP_STARTED:
                    # The relay only starts a desktop after the person accepted, so this
                    # event IS the consent — there is no separate "accepted" message.
                    if remote_session.status is RemoteSessionStatus.PENDING:
                        await service.record_response(
                            session_id=remote_session.id, accepted=True
                        )
                    await service.mark_active(
                        session_id=remote_session.id,
                        provider_session_id=event.session_id,
                    )
                else:
                    await service.end(session_id=remote_session.id, actor=None)
            except (ConflictError, NotFoundError) as exc:
                # A session that moved on between the read and the write. Not worth
                # failing the listener over — the next event, or the sweep, settles it.
                logger.info("remote session %s ignored event %s: %s",
                            remote_session.id, event.msgid, exc)
                return False
            return True

    async def _open_session_for_node(self, session, node_id: str) -> RemoteSession | None:
        result = await session.execute(
            select(RemoteSession)
            .join(Device, Device.id == RemoteSession.device_id)
            .where(
                Device.meshcentral_node_id == node_id,
                RemoteSession.status.in_(list(OPEN_STATUSES)),
            )
            .order_by(RemoteSession.requested_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    # -- The loops ------------------------------------------------------------

    async def sweep_forever(self) -> None:
        """Retire prompts nobody answered, for as long as this process lives. Sweeps every
        SWEEP_INTERVAL while a session could still lapse, otherwise idles until a relay event
        or IDLE_SWEEP_INTERVAL, so an unused fleet doesn't keep the database awake."""
        while True:
            # Cleared BEFORE the sweep, so an event that lands mid-sweep still cuts the wait.
            self._wake.clear()
            busy = True
            try:
                async with self.session_factory() as session:
                    service = RemoteControlService(session)
                    moved = await service.expire_stale()
                    busy = await service.any_awaiting_expiry()
                if moved:
                    logger.info("retired %s unanswered remote session(s)", moved)
            except Exception:
                # A failed sweep must not stop the next one: every tick it misses is a
                # request left showing "waiting" to somebody watching the portal.
                logger.exception("remote session sweep failed")
            interval = SWEEP_INTERVAL if busy else IDLE_SWEEP_INTERVAL
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._wake.wait(), timeout=interval)

    async def listen_forever(self) -> None:
        """Hold the relay connection, reconnecting when it drops."""
        while True:
            try:
                async for event in self.client.stream():
                    await self.handle(event)
            except MeshCentralNotConfigured:
                logger.warning("No relay configured — the listener has nothing to do.")
                return
            except Exception:
                logger.exception("relay connection lost; reconnecting")
            await asyncio.sleep(RECONNECT_DELAY)

    async def run(self) -> None:
        await asyncio.gather(self.listen_forever(), self.sweep_forever())
