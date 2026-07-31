"""Feature tiers: give `plan` a meaning, and add per-org entitlement overrides

`plan` was a free-text label — "trial" or "per-seat" — that nothing read. The site now sells
three per-device tiers, so the column becomes the thing that decides what an org may use, and
`entitlement_overrides` carries the handful of deliberate exceptions.

EVERY EXISTING ORG IS SET TO 'expert'. That is the whole point of this migration being
careful: these organisations have had every feature since they signed up, and enforcement
lands in the same release. Mapping them to anything else would take paid functionality away
from live customers the moment this deploys — worse than the billing leak it fixes. The
operator downgrades each account deliberately, from the console, with the customer knowing.

Revision ID: 0038
Revises: 0037
Create Date: 2026-07-31
"""
import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("entitlement_overrides", sa.JSON(), nullable=True),
    )
    # Deliberately every row, not just the paid ones: an org still on trial is mid-evaluation
    # and should keep seeing the whole product.
    op.execute("UPDATE organizations SET plan = 'expert'")


def downgrade() -> None:
    op.drop_column("organizations", "entitlement_overrides")
    # `plan` is left as-is. Restoring "trial"/"per-seat" would be inventing history — the
    # old values carried no information that anything read.
