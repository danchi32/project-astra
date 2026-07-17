"""Provider-agnostic billing linkage (Razorpay for India, Paddle international)

Revision ID: 0024
Revises: 0023
Create Date: 2026-07-17
"""
import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("billing_provider", sa.String(length=20), nullable=True))
    op.add_column("organizations", sa.Column("provider_customer_id", sa.String(length=80), nullable=True))
    op.add_column("organizations", sa.Column("provider_subscription_id", sa.String(length=80), nullable=True))
    op.create_index("ix_organizations_provider_customer_id", "organizations", ["provider_customer_id"])
    op.create_index(
        "ix_organizations_provider_subscription_id", "organizations", ["provider_subscription_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_organizations_provider_subscription_id", table_name="organizations")
    op.drop_index("ix_organizations_provider_customer_id", table_name="organizations")
    op.drop_column("organizations", "provider_subscription_id")
    op.drop_column("organizations", "provider_customer_id")
    op.drop_column("organizations", "billing_provider")
