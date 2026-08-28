"""Record terms acceptance, and give invoices a seller identity.

Two changes that both exist because ASTRA is now sold by a registered company.

**organizations.terms_\\*** — signup previously created an organisation, started a trial
and enrolled devices with no terms of any kind. An e-contract is enforceable only if
acceptance can be shown, so the version, the moment and the source address are recorded
against the organisation. Nullable: organisations that predate this have no acceptance,
and a null is precisely how those accounts are found and asked to re-accept. Inventing a
value would destroy that signal.

**invoices.seller_\\*, sac_code, place_of_supply, cgst/sgst/igst, export_endorsement** —
an Indian tax invoice must carry the supplier's name, address and GSTIN, the SAC, the
place of supply, and the tax split shown separately. The seller details are *snapshotted*
onto each row rather than read from settings when the document renders: a company address
can change, and a GSTIN will be issued after some of these rows already exist, so reading
live settings would silently rewrite history on reprint.

`tax_cents` is deliberately left alone as the total. Every existing caller and the
portal's totals keep working; the three new columns only break that total down.

Nothing is backfilled. Where Paddle is the Merchant of Record it — not this company — is
the seller, and stamping our identity onto those rows would create a tax document naming
the wrong party.

Revision ID: 0054
Revises: 0053
"""
import sqlalchemy as sa
from alembic import op

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("terms_version", sa.String(length=20), nullable=True))
    op.add_column(
        "organizations",
        sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    # 45 characters so a full IPv6 address fits.
    op.add_column("organizations", sa.Column("terms_accepted_ip", sa.String(length=45), nullable=True))

    op.add_column("invoices", sa.Column("seller_legal_name", sa.String(length=200), nullable=True))
    op.add_column("invoices", sa.Column("seller_address", sa.String(length=400), nullable=True))
    op.add_column("invoices", sa.Column("seller_cin", sa.String(length=30), nullable=True))
    op.add_column("invoices", sa.Column("seller_gstin", sa.String(length=20), nullable=True))
    op.add_column("invoices", sa.Column("sac_code", sa.String(length=10), nullable=True))
    op.add_column("invoices", sa.Column("place_of_supply", sa.String(length=60), nullable=True))
    # Non-null with a server default so existing rows land on 0 rather than NULL — these
    # are amounts, and a null amount would have to be coalesced at every read site.
    for column in ("cgst_cents", "sgst_cents", "igst_cents"):
        op.add_column(
            "invoices",
            sa.Column(column, sa.Integer(), nullable=False, server_default="0"),
        )
    op.add_column("invoices", sa.Column("export_endorsement", sa.String(length=200), nullable=True))


def downgrade() -> None:
    for column in (
        "export_endorsement",
        "igst_cents",
        "sgst_cents",
        "cgst_cents",
        "place_of_supply",
        "sac_code",
        "seller_gstin",
        "seller_cin",
        "seller_address",
        "seller_legal_name",
    ):
        op.drop_column("invoices", column)

    for column in ("terms_accepted_ip", "terms_accepted_at", "terms_version"):
        op.drop_column("organizations", column)
