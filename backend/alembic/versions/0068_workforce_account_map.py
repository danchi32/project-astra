"""Workforce Insights ("Tracker") — account → directory-user mapping.

Adds activity_accounts, mapping a tracked Windows account (ACME\\rahul) to a directory user,
so attendance and productivity can roll up by person and team. Unmapped accounts (user_id
NULL) still track; the mapping only adds identity on top. SET NULL on user delete.

Revision ID: 0068
Revises: 0067
"""
import sqlalchemy as sa
from alembic import op

from app.models.base import GUID

revision = "0068"
down_revision = "0067"
branch_labels = None
depends_on = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_table("activity_accounts")
