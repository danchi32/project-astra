"""Billing profile per organization, and invoice records

Two additive tables. Nothing existing is touched, so this is safe to apply ahead of the code
that reads it and safe to leave in place if that code is rolled back.

Indexes are on the columns the operator's billing screen actually filters and sorts by —
org, issue date, status and renewal — rather than on everything, because an index that no
query uses is write cost with no read benefit.

Revision ID: 0039
Revises: 0038
Create Date: 2026-07-31
"""
import sqlalchemy as sa
from alembic import op

from app.models.base import GUID

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Sorting the operator's organization list by recent activity needs something to sort on.
    # Backfilled to created_at rather than to now(), so an untouched org doesn't claim to
    # have been updated at deploy time.
    op.add_column(
        "organizations",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE organizations SET updated_at = created_at WHERE updated_at IS NULL")
    op.alter_column("organizations", "updated_at", nullable=False)

    op.create_table(
        "organization_billing_profiles",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("org_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, unique=True, index=True),
        sa.Column("legal_name", sa.String(length=200), nullable=True),
        sa.Column("billing_contact_name", sa.String(length=150), nullable=True),
        sa.Column("billing_email", sa.String(length=255), nullable=True),
        sa.Column("address_line1", sa.String(length=200), nullable=True),
        sa.Column("address_line2", sa.String(length=200), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True, index=True),
        # Label + value rather than a column per tax regime: "GSTIN"/"VAT"/"ABN" all print
        # the same way on an invoice, and a gst_number column would need a sibling for every
        # country ASTRA ever sells into.
        sa.Column("tax_id_label", sa.String(length=20), nullable=True),
        sa.Column("tax_id", sa.String(length=50), nullable=True),
        sa.Column("registration_number", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "invoices",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("org_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("number", sa.String(length=40), nullable=False, unique=True, index=True),
        sa.Column("issued_on", sa.Date(), nullable=False, index=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("plan", sa.String(length=40), nullable=True),
        sa.Column("seats", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        # Minor units. A float column here is a rounding drift you get to explain to a
        # customer holding a bank statement.
        sa.Column("subtotal_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("discount_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tax_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open", index=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("renews_on", sa.Date(), nullable=True, index=True),
        sa.Column("provider", sa.String(length=20), nullable=True, index=True),
        sa.Column("provider_invoice_id", sa.String(length=80), nullable=True, index=True),
        sa.Column("transaction_id", sa.String(length=80), nullable=True, index=True),
        sa.Column("payment_method", sa.String(length=40), nullable=True),
        sa.Column("provider_invoice_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    # The operator's billing list is "this org's invoices, newest first" — one composite
    # index serves it, where two single-column ones would leave the sort to the planner.
    op.create_index("ix_invoices_org_issued", "invoices", ["org_id", "issued_on"])


def downgrade() -> None:
    op.drop_index("ix_invoices_org_issued", table_name="invoices")
    op.drop_table("invoices")
    op.drop_table("organization_billing_profiles")
    op.drop_column("organizations", "updated_at")
