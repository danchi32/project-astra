"""Licensed seats + operator discount on organizations

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-15
"""
import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("license_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("organizations", sa.Column("discount_percent", sa.Integer(), nullable=True))
    op.add_column("organizations", sa.Column("stripe_coupon_id", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("organizations", "stripe_coupon_id")
    op.drop_column("organizations", "discount_percent")
    op.drop_column("organizations", "license_count")
