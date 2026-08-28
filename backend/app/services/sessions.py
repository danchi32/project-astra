"""The fleet's logon sessions, and the four things a technician does to one.

Reading is a straight query over `device_sessions` joined to `devices`. Acting is not a new
mechanism: every action here goes through RemediationService like any other remediation, so
it inherits the tier check, the approval record, the audit entry, the duplicate guard and
the fleet circuit breaker. Adding a second, shorter path to the agent for "just a lock" is
how a system ends up with commands nobody can account for afterwards.
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, RemediationSource, RemediationTask, User
from app.models.base import as_utc, utcnow
from app.repositories.devices import DeviceRepository
from app.repositories.sessions import SessionRepository
from app.schemas.devices import ONLINE_THRESHOLD
from app.schemas.sessions import DeviceSessionPage, DeviceSessionRead, SessionCounts
from app.services.exceptions import NotFoundError
from app.services.remediation.service import RemediationService

# Portal-facing action ids that address a single logon session. Kept as a set here, and as
# real entries in the remediation registry, so the endpoint can reject an unknown id with a
# useful message before any of the heavier machinery starts.
SESSION_ACTIONS: frozenset[str] = frozenset(
    {"lock_session", "logoff_session", "message_session", "reset_local_password"}
)


class SessionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = SessionRepository(session)
        self.devices = DeviceRepository(session)
        self.remediation = RemediationService(session)

    async def list_page(
        self,
        *,
        actor: User,
        q: str | None = None,
        state: str | None = None,
        connection: str | None = None,
        group_id: uuid.UUID | None = None,
        online: bool | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> DeviceSessionPage:
        cutoff = utcnow() - ONLINE_THRESHOLD
        rows, total = await self.repo.page(
            actor.org_id, q=q, state=state, connection=connection, group_id=group_id,
            online=online, online_cutoff=cutoff,
            offset=(page - 1) * page_size, limit=page_size,
        )
        counts = await self.repo.counts(
            actor.org_id, q=q, group_id=group_id, online=online, online_cutoff=cutoff,
        )
        groups = await self.repo.group_names_for({d.id for _, d in rows})

        return DeviceSessionPage(
            items=[
                DeviceSessionRead(
                    id=s.id,
                    device_id=d.id,
                    hostname=d.hostname,
                    session_id=s.session_id,
                    username=s.username,
                    state=s.state,           # type: ignore[arg-type]
                    connection=s.connection,  # type: ignore[arg-type]
                    station=s.station,
                    client_name=s.client_name,
                    logon_at=s.logon_at,
                    idle_seconds=s.idle_seconds,
                    device_online=(
                        d.last_seen_at is not None and as_utc(d.last_seen_at) >= cutoff
                    ),
                    device_last_seen_at=d.last_seen_at,
                    groups=groups.get(d.id, []),
                )
                for s, d in rows
            ],
            total=total,
            counts=SessionCounts(**counts),
        )

    async def for_device(
        self, *, actor: User, device_id: uuid.UUID
    ) -> list[DeviceSessionRead]:
        """Sessions on one device, for the device page's own Sessions tab."""
        device = await self.devices.get(device_id)
        if device is None or device.org_id != actor.org_id:
            raise NotFoundError("Device not found.")

        cutoff = utcnow() - ONLINE_THRESHOLD
        online = device.last_seen_at is not None and as_utc(device.last_seen_at) >= cutoff
        groups = await self.repo.group_names_for({device.id})
        return [
            DeviceSessionRead(
                id=s.id,
                device_id=device.id,
                hostname=device.hostname,
                session_id=s.session_id,
                username=s.username,
                state=s.state,           # type: ignore[arg-type]
                connection=s.connection,  # type: ignore[arg-type]
                station=s.station,
                client_name=s.client_name,
                logon_at=s.logon_at,
                idle_seconds=s.idle_seconds,
                device_online=online,
                device_last_seen_at=device.last_seen_at,
                groups=groups.get(device.id, []),
            )
            for s in await self.repo.for_device(device.id)
        ]

    async def act(
        self,
        *,
        actor: User,
        device_id: uuid.UUID,
        action_id: str,
        session_id: int,
        message: str | None = None,
        username: str | None = None,
        reason: str | None = None,
    ) -> RemediationTask:
        """Push one session action to a device.

        The Windows session id travels as a remediation parameter. That matters: without it
        every action here would mean "whichever session the agent felt was the interactive
        one", which on a terminal server with thirty people signed in is a coin flip, and
        the coin decides whose work gets closed.
        """
        if action_id not in SESSION_ACTIONS:
            raise NotFoundError(f"'{action_id}' is not a session action.")

        device = await self.devices.get(device_id)
        if device is None or device.org_id != actor.org_id:
            raise NotFoundError("Device not found.")

        params: dict[str, str] = {"session_id": str(session_id)}
        if action_id == "message_session":
            params["message"] = message or ""
        if action_id == "reset_local_password":
            # The account, not the session: a password belongs to a user, and the session
            # only tells us which one to prefill in the portal.
            params["username"] = username or ""

        return await self.remediation.create_task(
            org_id=actor.org_id,
            device=device,
            action_id=action_id,
            params=params,
            reason=reason or _default_reason(action_id, session_id, device),
            source=RemediationSource.USER,
            actor_user_id=actor.id,
            approver=actor,   # the person clicking IS the approver; tiers still checked
        )


def _default_reason(action_id: str, session_id: int, device: Device) -> str:
    """A reason the audit log can be read from six months later without the UI beside it.

    The endpoint accepts a typed reason and uses it when given; this is the fallback, and it
    is deliberately specific rather than "portal action" — an audit line that does not say
    which session on which machine is a line nobody can act on.
    """
    what = {
        "lock_session": "Lock session",
        "logoff_session": "Sign out session",
        "message_session": "Send a message to session",
        "reset_local_password": "Reset the local password for session",
    }[action_id]
    return f"{what} {session_id} on {device.hostname} from the portal Sessions view"
