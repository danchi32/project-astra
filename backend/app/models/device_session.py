import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin

# Windows' WTS_CONNECTSTATE_CLASS, narrowed to the two states that mean a person has a
# desktop on this machine. Everything else (listening, connecting, shadowing) is a
# transport detail of the terminal-services stack, not a user, and is dropped by the agent.
SESSION_ACTIVE = "active"              # signed in, at the desktop
SESSION_DISCONNECTED = "disconnected"  # still signed in, session detached (RDP closed, switched user)

# How the person is attached to the machine. Worth keeping separate from state, because
# "disconnected console" and "disconnected RDP" mean different things to a technician:
# the first is a locked/switched-away desktop, the second is someone who closed a remote
# window and left their programs running.
SESSION_CONSOLE = "console"
SESSION_RDP = "rdp"


class DeviceSession(TimestampMixin, Base):
    """One Windows logon session on a device, as the agent enumerated it.

    Devices already carry `logged_in_user`, which is the CONSOLE user and only ever one
    name. That is enough to label a laptop and useless for anything else: a terminal server
    with 30 people on it reports one of them, a machine someone left signed in over RDP
    while a second person uses the console reports whichever the WTS console query answers
    with, and neither case is visible at all. This table is the whole picture.

    Rows are replaced only when the set actually changes — see Device.sessions_hash. A
    session's freshness is the device's own `last_seen_at`; storing a per-row timestamp
    would mean writing every row of every device every minute for information the device
    row already carries.
    """

    __tablename__ = "device_sessions"
    __table_args__ = (
        UniqueConstraint("device_id", "session_id", name="uq_device_sessions_device_session"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)

    # Windows' own session id. Needed as more than a label: every action against a session
    # (log off, lock, message) is addressed to this number, so it has to survive the round
    # trip from the agent, through the portal, and back to the agent as a parameter.
    session_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # DOMAIN\user as the session's own token reports it. Nullable because a session can
    # exist with no user attached yet (a listener that has not been dropped, a machine at
    # the logon screen) — the portal shows those as "(no user)" rather than hiding them,
    # because "nobody is signed in" is a real answer to "who is on that machine".
    username: Mapped[str | None] = mapped_column(String(150), nullable=True)

    state: Mapped[str] = mapped_column(String(20), nullable=False)          # active | disconnected
    connection: Mapped[str] = mapped_column(String(20), nullable=False)     # console | rdp

    # The WinStation name ("Console", "RDP-Tcp#3"). Kept verbatim: when two RDP sessions
    # look identical in every other column, this is what tells them apart.
    station: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # Where an RDP session is coming FROM — the client's own machine name. Null on console
    # sessions. This is the field that answers "who is remoting into this server".
    client_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    logon_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Seconds since the session last saw input. Windows reports it per session; a long idle
    # on an active session is how a technician tells "working" from "left the desk".
    idle_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
