import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin


class RemoteSessionStatus(str, enum.Enum):
    """Where a request for someone's screen has got to.

    DECLINED and NO_RESPONSE are separate on purpose, and the distinction is the whole
    reason this enum is not a boolean. A refusal is an answer: the technician has been told
    no and should stop. Silence is not an answer: the person was in a meeting, or the
    prompt opened behind a full-screen window, and the right next move is to try again or
    call them. The remote-control engine reports both as a rejection; a technician reading
    that concluded a customer had refused a session the customer never saw.
    """

    PENDING = "pending"            # asked; waiting on the person at the keyboard
    APPROVED = "approved"          # they said yes — the viewer may be opened
    ACTIVE = "active"              # the technician is connected
    ENDED = "ended"                # finished, by either side
    DECLINED = "declined"          # they said no
    NO_RESPONSE = "no_response"    # they never answered (NOT the same as declined)
    EXPIRED = "expired"            # approved, but nobody opened the viewer in time
    FAILED = "failed"              # the remote-control service could not start it


#: The statuses a session can still move on from. Everything else is final, and a caller
#: acting on a finished session is a bug worth a clear refusal rather than a silent no-op.
OPEN_STATUSES = frozenset({
    RemoteSessionStatus.PENDING,
    RemoteSessionStatus.APPROVED,
    RemoteSessionStatus.ACTIVE,
})


class RemoteSession(TimestampMixin, Base):
    """One request to view and control one device, and what came of it."""

    __tablename__ = "remote_sessions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)
    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Not nullable: a session nobody is accountable for must not be able to exist. Unlike
    # a remediation task, there is no "the assistant did it" case to leave room for — the
    # AI cannot reach this feature at all.
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False)

    # The technician's own words, shown to the person being asked. A prompt that cannot say
    # why is a prompt people learn to click through without reading.
    reason: Mapped[str] = mapped_column(String(500), nullable=False)

    status: Mapped[RemoteSessionStatus] = mapped_column(
        Enum(RemoteSessionStatus, native_enum=False, length=20,
             values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=RemoteSessionStatus.PENDING,
        index=True,
    )

    #: The remote-control engine's own handle for this session, once it has one.
    provider_session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: Where the recording lives, for the orgs that turn recording on. Nothing writes this
    #: yet; the column exists so that switching recording on later is a feature rather than
    #: a migration against a table full of live rows.
    recording_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
