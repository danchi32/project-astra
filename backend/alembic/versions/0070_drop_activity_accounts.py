"""Workforce Insights ("Tracker") — drop the manual account→user map.

The tracked account now resolves to a person through the device's Assets assignment
(daily_user_summary.user_id is stamped from it at recompute), so the separate
activity_accounts mapping and its UI are gone. This drops the now-unused table.

Revision ID: 0070
Revises: 0069
"""
import sqlalchemy as sa
from alembic import op

from app.models.base import GUID

revision = "0070"
down_revision = "0069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("activity_accounts")


def downgrade() -> None:
    op.create_table(
        "activity_accounts",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("org_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("username", sa.String(length=150), nullable=False),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("org_id", "username", name="uq_activity_accounts_org_user"),
    )
