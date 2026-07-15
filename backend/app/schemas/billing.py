"""Billing (Stripe) request/response schemas."""
from datetime import datetime

from pydantic import BaseModel, Field


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
    licenses: int                  # purchased licenses (0 = trial/unlicensed → uncapped)
    seats_used: int                # active devices/users consuming a license
    discount_percent: int | None   # operator-applied discount, if any
    unit_price_configured: bool    # a Stripe price is set on the server


class CheckoutRequest(BaseModel):
    quantity: int = Field(default=1, ge=1, description="Number of licenses to buy")


class LicenseUpdate(BaseModel):
    count: int = Field(ge=1, description="New total number of licenses")


class CheckoutSession(BaseModel):
    url: str


class PortalSession(BaseModel):
    url: str


class LicenseResult(BaseModel):
    licenses: int
    seats_used: int
    detail: str
