import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin


class SupportRequestStatus(str, enum.Enum):
    OPEN = "open"                        # nobody at ASTRA has picked it up
    IN_PROGRESS = "in_progress"          # being worked on
    WAITING_CUSTOMER = "waiting_customer"  # we replied; the ball is with them
    RESOLVED = "resolved"                # fixed, and they have been told
    CLOSED = "closed"                    # no further action


class SupportRequestPriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class SupportRequest(TimestampMixin, Base):
    """A customer asking ASTRA itself for help.

    Not to be confused with `SupportEscalation`, which is the opposite direction: that one
    hands an end user's problem to the CUSTOMER's own helpdesk. This one is an organization
    raising a problem with us, and it is the only channel in the product where they can.

    The `diagnostics` snapshot is what makes this worth building rather than pointing
    people at an email address. Everything needed to understand the request — plan, fleet
    size, how many devices are actually reporting in, which agent versions are deployed,
    what has been failing — already exists in this database. Captured at submit time, a
    request arrives explained instead of as "it doesn't work", and it keeps explaining
    itself a week later when the fleet has moved on.
    """

    __tablename__ = "support_requests"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Kept if the person who raised it later leaves, so the thread does not lose its author.
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    #: Short, human-quotable reference — "SUP-4F2A9C". Unique so a customer naming it in an
    #: email lands on exactly one thread.
    reference: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)

    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    #: One of schemas.help_centre.HELP_CATEGORIES, so a request and the help article that
    #: answers it are filed under the same word.
    category: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)

    status: Mapped[SupportRequestStatus] = mapped_column(
        Enum(SupportRequestStatus, native_enum=False, length=20,
             values_callable=lambda e: [m.value for m in e]),
        nullable=False, default=SupportRequestStatus.OPEN, index=True,
    )
    priority: Mapped[SupportRequestPriority] = mapped_column(
        Enum(SupportRequestPriority, native_enum=False, length=10,
             values_callable=lambda e: [m.value for m in e]),
        nullable=False, default=SupportRequestPriority.NORMAL, index=True,
    )

    #: Captured server-side at submit. Never accepted from the client: a support ticket
    #: that reports whatever the browser claimed is a ticket that can lie about the fleet.
    diagnostics: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    #: Drives the queue ordering without joining the message table on every list.
    last_reply_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class SupportRequestMessage(TimestampMixin, Base):
    """One message in a support thread, from either side.

    Without replies this whole feature is a suggestion box: the customer writes into it and
    never learns whether anyone read it, which is worse for satisfaction than having no
    channel at all.
    """

    __tablename__ = "support_request_messages"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("support_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    #: Which side wrote it. Stored rather than inferred from the author's org, because a
    #: platform operator answering through view-as would otherwise look like the customer.
    from_operator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    body: Mapped[str] = mapped_column(String(10000), nullable=False)
