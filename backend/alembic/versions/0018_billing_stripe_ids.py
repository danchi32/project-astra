"""Add Stripe customer/subscription linkage to organizations

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-14
"""
import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("stripe_customer_id", sa.String(length=64), nullable=True))
    op.add_column("organizations", sa.Column("stripe_subscription_id", sa.String(length=64), nullable=True))
    op.create_index("ix_organizations_stripe_customer_id", "organizations", ["stripe_customer_id"])
    op.create_index("ix_organizations_stripe_subscription_id", "organizations", ["stripe_subscription_id"])


def downgrade() -> None:
    op.drop_index("ix_organizations_stripe_subscription_id", table_name="organizations")
    op.drop_index("ix_organizations_stripe_customer_id", table_name="organizations")
    op.drop_column("organizations", "stripe_subscription_id")
    op.drop_column("organizations", "stripe_customer_id")
