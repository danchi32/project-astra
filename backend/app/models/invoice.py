import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin


class InvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    OPEN = "open"            # issued, not yet paid
    PAID = "paid"
    FAILED = "failed"        # payment attempted and declined
    REFUNDED = "refunded"
    VOID = "void"


class Invoice(TimestampMixin, Base):
    """One billing event, stored so the customer and the operator can look it back up.

    ASTRA records every invoice; it does not necessarily ISSUE every invoice. On Paddle,
    Paddle is the Merchant of Record — legally the seller — and issues the compliant
    document itself, so those rows carry `provider_invoice_url` and ASTRA renders nothing.
    On Razorpay, ASTRA is the seller and must produce its own tax invoice, which is what the
    billing profile's legal name and tax id are for. Generating our own document for a Paddle
    sale would be a tax document naming the wrong seller.

    Money is stored in minor units (paise, cents) as integers. Floats are not a currency
    type, and a rounding drift in a financial record is not something you can explain away
    to a customer.
    """

    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Human-facing reference. Unique so a customer quoting "ASTRA-2026-0043" always lands on
    # exactly one record.
    number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)
    issued_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    # The plan as it was at billing time. Denormalised on purpose: an invoice must keep
    # saying what was actually sold even after the org upgrades.
    plan: Mapped[str | None] = mapped_column(String(40), nullable=True)
    seats: Mapped[int | None] = mapped_column(Integer, nullable=True)

    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    subtotal_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tax_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, native_enum=False, length=20,
             values_callable=lambda e: [m.value for m in e]),
        nullable=False, default=InvoiceStatus.OPEN, index=True,
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # When the subscription this invoice covers renews — the operator's "what is coming up"
    # and "what lapsed" view is built on this.
    renews_on: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)

    # "razorpay" | "paddle" | "paypal". Which rail this was billed on, and its ids, so a
    # support question can be traced back to the provider's own dashboard.
    provider: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    provider_invoice_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    transaction_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    payment_method: Mapped[str | None] = mapped_column(String(40), nullable=True)
    #: Set when the PROVIDER is the seller of record (Paddle). Present means: link to this,
    #: don't render our own document.
    provider_invoice_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
