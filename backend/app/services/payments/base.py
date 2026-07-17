"""Payment-rail abstraction.

ASTRA sells to Indian *and* international customers, which need different rails:
  * Razorpay — India (UPI / cards / netbanking / e-mandate, INR).
  * Paddle   — international (Merchant of Record: cards worldwide, global VAT).

Everything above this layer (trial gate, license cap, discounts, the Platform
console) is rail-agnostic. A provider's only job is: send the admin somewhere to
pay, and turn that rail's webhooks into a normalized SubscriptionEvent we can
apply to the organization.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.models import Organization, SubscriptionStatus


@dataclass
class SubscriptionEvent:
    """A rail's webhook, normalized. Any field may be None if the rail didn't say."""
    org_id: UUID | None = None
    customer_id: str | None = None
    subscription_id: str | None = None
    status: SubscriptionStatus | None = None
    quantity: int | None = None          # purchased licenses
    period_end: datetime | None = None
    ignored: bool = False                # event we don't care about


class PaymentProvider(Protocol):
    """One payment rail. Implementations must be inert until configured."""

    name: str

    @property
    def enabled(self) -> bool:
        """Credentials present — the rail can be talked to at all."""
        ...

    @property
    def can_checkout(self) -> bool:
        """Enough config to actually sell (credentials + a per-seat plan/price)."""
        ...

    async def create_checkout(self, *, org: Organization, quantity: int) -> str:
        """Return a URL to redirect the admin to, to authorize payment."""
        ...

    async def set_quantity(self, *, org: Organization, quantity: int) -> None:
        """Change purchased licenses on an existing subscription."""
        ...

    async def cancel(self, *, org: Organization) -> None:
        """Cancel the org's subscription."""
        ...

    def manage_url(self, org: Organization) -> str | None:
        """Hosted self-serve management page, if the rail has one (Paddle does,
        Razorpay doesn't — we expose an in-app cancel instead)."""
        ...

    async def parse_webhook(self, *, payload: bytes, headers: dict[str, str]) -> SubscriptionEvent:
        """Verify authenticity and normalize. Raise ValidationError if invalid.

        Async because verification isn't always local: Razorpay/Paddle check an HMAC
        in-process, but PayPal requires a round-trip to its verify-webhook-signature
        API. This is the security boundary — a forged webhook must never mark an org
        as paid, so every implementation MUST verify before returning an event.
        """
        ...
