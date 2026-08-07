import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin


class EscalationState(str, enum.Enum):
    OFFERED = "offered"    # ASTRA asked; nobody has answered yet
    RAISED = "raised"      # a ticket exists in the customer's helpdesk
    DECLINED = "declined"  # the user said no
    FAILED = "failed"      # we tried to raise it and the helpdesk refused or was down


class SupportEscalation(TimestampMixin, Base):
    """One problem ASTRA could not fix, handed to a human.

    Three jobs in one row, which is why it exists as a table rather than a log line:

      1. **Consent.** A row in `offered` is the record that ASTRA asked. Raising a ticket
         checks for it, so "ask before raising" is enforced in code rather than hoped for
         in a prompt — the same rule the remediation tiers already follow.
      2. **Deduplication.** A user who reports the same thing three times because nothing
         has visibly happened must not produce three tickets. Three tickets for one problem
         wrecks the customer's SLA reporting, and an IT manager whose queue fills with
         duplicates switches the integration off. That is how this feature dies.
      3. **The record.** Which ticket was raised, where, and when — so the assistant can
         answer "you already have ticket #123" instead of opening another.

    ASTRA is not the system of record for the ticket. The customer's helpdesk owns its
    lifecycle; this row only remembers that we handed it over.
    """

    __tablename__ = "support_escalations"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True, index=True)
    device_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True, index=True)
    # Who the ticket is raised on behalf of. Null when the chat came from a device with no
    # signed-in user we can identify — the adapter then falls back to the org's default.
    user_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True, index=True)

    # The user's own words. Deliberately not a summary: it is what the requester typed,
    # and it is what a technician reading the ticket needs to see first.
    problem_summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    # Scored against later reports to recognise "this again". Same vector space as the
    # knowledge base, so the model tag has to travel with it for the same reason.
    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(60), nullable=True)

    # What ASTRA last tried, if anything. Drives the helpdesk category, so a ticket lands
    # in the right queue instead of a generic bucket.
    action_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Rendered at offer time and kept: the evidence as it stood when we escalated. If the
    # device is fixed or wiped tomorrow, the ticket still explains why it was raised.
    dossier: Mapped[str | None] = mapped_column(String(20000), nullable=True)

    state: Mapped[EscalationState] = mapped_column(
        Enum(EscalationState, native_enum=False, length=20,
             values_callable=lambda e: [m.value for m in e]),
        nullable=False, default=EscalationState.OFFERED, index=True,
    )

    provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    external_ticket_id: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    external_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)

    raised_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
