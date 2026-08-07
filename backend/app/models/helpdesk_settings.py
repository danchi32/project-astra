import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin, utcnow


class HelpdeskSettings(TimestampMixin, Base):
    """One organization's connection to the ticketing system they already run.

    ASTRA is not the ticketing system. This row is what lets it hand a ticket to theirs —
    which is the answer to "why would we pay for two". Nothing here is global: every
    organization brings its own instance, its own credential, and its own idea of what a
    category means.

    Absent or disabled, the escalation path is inert: the assistant never offers to raise a
    ticket, because it has nowhere to raise one.
    """

    __tablename__ = "helpdesk_settings"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True,
    )

    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="freshservice")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Their instance: "acme" in acme.freshservice.com.
    domain: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Fernet ciphertext, never the key itself. This credential can read every ticket and
    # contact in their helpdesk, so it does not sit in a column in the clear.
    api_key_encrypted: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Freshservice priority ids: 1 Low, 2 Medium, 3 High, 4 Urgent. ASTRA does not decide
    # how urgent a customer's problems are — it files at the level they chose.
    default_priority: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Source id, so their reporting can tell ASTRA's tickets apart. Tags carry the same
    # signal and need no admin setup, which is why this is optional.
    default_source: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Accounts with more than one workspace need tickets pointed at the right one, or they
    # land somewhere nobody is watching.
    workspace_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Optional group to file into. Left unset by default so their own assignment rules
    # decide, which they are better at than we are.
    group_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # {action_id: {"category": ..., "sub_category": ...}} — ASTRA's remediation actions
    # mapped onto this org's category tree, so a ticket lands in the queue that handles
    # that kind of problem instead of a generic bucket. Every org's tree is its own, so
    # there is no useful default: unset means send no category and let them triage.
    category_map: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
