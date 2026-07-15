"""Org subscription/trial fields + platform-admin flag

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-14
"""
import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing orgs become 'trialing' with no trial_ends_at, which org_is_writable
    # treats as writable — so nothing gets locked out by this migration.
    op.add_column("organizations", sa.Column("plan", sa.String(40), nullable=False, server_default="trial"))
    op.add_column(
        "organizations",
        sa.Column("subscription_status", sa.String(20), nullable=False, server_default="trialing"),
    )
    op.add_column("organizations", sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("organizations", sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True))

    op.add_column(
        "users",
        sa.Column("is_platform_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("users", "is_platform_admin")
    op.drop_column("organizations", "current_period_end")
    op.drop_column("organizations", "trial_ends_at")
    op.drop_column("organizations", "subscription_status")
    op.drop_column("organizations", "plan")
