"""Billing identity and invoice records, as the API exposes them."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.invoice import InvoiceStatus


class BillingProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    legal_name: str | None = None
    billing_contact_name: str | None = None
    billing_email: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country_code: str | None = None
    tax_id_label: str | None = None
    tax_id: str | None = None
    registration_number: str | None = None
    #: False until the fields an invoice actually needs are present. Computed rather than
    #: stored so it can never disagree with the row.
    complete: bool = False


class BillingProfileUpdate(BaseModel):
    """Every field optional: this is filled in over time, usually by someone in finance who
    has half the details to hand. Rejecting a partial save would just mean it never gets
    saved at all."""

    legal_name: str | None = Field(default=None, max_length=200)
    billing_contact_name: str | None = Field(default=None, max_length=150)
    billing_email: EmailStr | None = None
    address_line1: str | None = Field(default=None, max_length=200)
    address_line2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    tax_id_label: str | None = Field(default=None, max_length=20)
    tax_id: str | None = Field(default=None, max_length=50)
    registration_number: str | None = Field(default=None, max_length=50)

    @field_validator("country_code")
    @classmethod
    def _upper(cls, v: str | None) -> str | None:
        # ISO 3166-1 alpha-2 is uppercase. Normalised on the way in so "in" and "IN" don't
        # become two different countries in a tax report.
        if v is None:
            return None
        v = v.strip().upper()
        if not v.isalpha():
            raise ValueError("Country must be a 2-letter ISO code, e.g. IN, GB, US.")
        return v

    @field_validator("tax_id", "registration_number", "legal_name", "billing_contact_name",
                     "address_line1", "address_line2", "city", "state", "postal_code",
                     "tax_id_label")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        # "" from an emptied form field means "clear this", not a value of empty string.
        if v is None:
            return None
        v = v.strip()
        return v or None


class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    number: str
    issued_on: date
    period_start: date | None
    period_end: date | None
    plan: str | None
    seats: int | None
    currency: str
    subtotal_cents: int
    discount_cents: int
    tax_cents: int
    total_cents: int
    status: InvoiceStatus
    paid_at: datetime | None
    renews_on: date | None
    provider: str | None
    transaction_id: str | None
    payment_method: str | None
    #: Where the document lives. Set for rails that issue it themselves (Paddle is Merchant
    #: of Record); null means ASTRA is the seller and renders its own.
    provider_invoice_url: str | None
    #: Only on the operator's cross-org view, so the list doesn't need a second lookup.
    org_name: str | None = None
