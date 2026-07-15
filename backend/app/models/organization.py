import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin


class SubscriptionStatus(str, enum.Enum):
    TRIALING = "trialing"      # in a free trial; writable until trial_ends_at
    ACTIVE = "active"          # paying; writable
    PAST_DUE = "past_due"      # payment failed; read-only
    SUSPENDED = "suspended"    # operator-suspended; read-only
    CANCELED = "canceled"      # subscription ended; read-only


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)

    # -- Subscription / lifecycle (managed by the platform operator + billing) --
    plan: Mapped[str] = mapped_column(String(40), nullable=False, default="trial")
    subscription_status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, native_enum=False, length=20,
             values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=SubscriptionStatus.TRIALING,
    )
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Stripe linkage (null until the org starts a paid subscription via Checkout).
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
