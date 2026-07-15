"""Billing (Stripe) request/response schemas."""
from datetime import datetime

from pydantic import BaseModel


class BillingStatus(BaseModel):
    """What the portal shows on the billing page for the caller's own org."""
    billing_enabled: bool          # is Stripe configured on the server at all?
    plan: str
    subscription_status: str
    writable: bool                 # can the org make changes right now?
    read_only_reason: str | None   # set when writable is False
    trial_ends_at: datetime | None
    current_period_end: datetime | None
    has_subscription: bool         # already has a live Stripe subscription
    seat_type: str                 # "device" or "user"
    seat_count: int                # current billable seats (live count)
    unit_price_configured: bool    # a Stripe price is set on the server


class CheckoutSession(BaseModel):
    url: str


class PortalSession(BaseModel):
    url: str


class SeatSyncResult(BaseModel):
    synced: bool
    seat_count: int
    detail: str
