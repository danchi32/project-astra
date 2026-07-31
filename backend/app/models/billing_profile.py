import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin


class OrganizationBillingProfile(TimestampMixin, Base):
    """Who to bill, and the legal identity to put on the invoice.

    Separate from `organizations` rather than more columns on it: this is data the customer
    owns and edits, most orgs never fill it in, and it is read almost exclusively at invoice
    time. Keeping it out of the row loaded on every request is the difference between a
    lookup and a wider table scan once there are thousands of orgs.

    Deliberately not modelled per tax regime. `tax_id_label` + `tax_id` holds "GSTIN" and a
    GSTIN for an Indian customer, "VAT" and a VAT number for an EU one, "ABN" for Australia —
    a `gst_number` column would have to be joined by `vat_number` and `abn` and every regime
    after that, and the invoice only ever needs to print the label and the value.
    """

    __tablename__ = "organization_billing_profiles"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )

    # The legal entity being invoiced, which is often not the name the org signed up under.
    legal_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    billing_contact_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    # Where invoices go. Separate from any user's login email — accounts payable is rarely
    # the person who administers the product.
    billing_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    address_line1: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # ISO 3166-1 alpha-2. Stored as the code, not the display name, so it can drive tax
    # treatment later without re-parsing free text.
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)

    # e.g. ("GSTIN", "29ABCDE1234F1Z5") or ("VAT", "DE123456789").
    tax_id_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
