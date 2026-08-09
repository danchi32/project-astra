import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin


class WebhookEvent(TimestampMixin, Base):
    """One billing webhook we have already applied.

    Signature verification proves a payload is authentic. It does not prove it is new. Every
    rail here signs the body (Paddle adds a timestamp but nothing checked its age), so a
    captured `subscription.activated` payload stayed valid forever — replay it after a
    cancellation and the org went back to ACTIVE, which is the flag `org_is_writable` reads.

    This row is the record that says "seen it". The unique constraint is the guard, not the
    application code: two deliveries racing each other both pass an `if exists` check, and
    only the database can decide which one wins.

    Rows are kept rather than pruned. They are small, and "which webhook changed this
    customer's subscription, and when" is a question billing disputes actually ask.
    """

    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_webhook_events_provider_event"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)

    # "paddle" | "razorpay" | "paypal" | "stripe"
    provider: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    # The rail's own id for this delivery.
    event_id: Mapped[str] = mapped_column(String(200), nullable=False)

    # Nullable: an event can be authentic, deduped, and still not resolve to an org we know.
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # When the RAIL says it happened, not when we received it. Ordering is decided on this.
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # What it did to the org, for the dispute conversation.
    applied_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
