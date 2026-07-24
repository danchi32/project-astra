import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String
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

    # The corporate email domain this org signed up with (e.g. "acme.com"), so a second
    # self-service signup from the same domain is refused — one organisation, one account.
    # Null for personal/free-mail signups (gmail, outlook, …), which may register freely.
    email_domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

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

    # Permanent per-org agent enrollment key, baked into that org's installer.
    # No expiry; rotated only on demand by an admin. Null only until first provisioned.
    agent_enrollment_key: Mapped[str | None] = mapped_column(
        String(80), nullable=True, unique=True, index=True
    )

    # Stripe linkage (null until the org starts a paid subscription via Checkout).
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # Which payment rail this org pays on: "razorpay" (India: UPI/cards/netbanking)
    # or "paddle" (international: Merchant of Record, handles global VAT). Set when
    # the org first checks out; null while on trial. Ids are provider-agnostic so a
    # new rail can be added without another migration.
    billing_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    provider_customer_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    provider_subscription_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)

    # Licensed seats: how many the org has purchased. 0 = unlicensed (trial / not
    # subscribed) and therefore uncapped. When > 0, device enrollment is hard-capped
    # at this number. Kept in sync with the Stripe subscription quantity.
    license_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # Operator-applied discount (super-admin only). Percent off, realised as a Stripe
    # coupon attached to the subscription + future checkouts.
    discount_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stripe_coupon_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Pro-AI entitlement (super-admin toggle). When False (Basic plan), the chat agent
    # answers only from its built-in engine/memory; when True (Pro), it may escalate to
    # the real Claude LLM — provided a platform Anthropic key is configured.
    ai_pro: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
