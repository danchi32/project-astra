"""Banned/restricted software list (compliance)

Adds the banned_software table: an org-scoped list of restricted application name
patterns. Purely additive — no existing table or column is touched.

Revision ID: 0034
Revises: 0033
Create Date: 2026-07-29
"""
import sqlalchemy as sa
from alembic import op

from app.models.base import GUID

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "banned_software",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("org_id", GUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("pattern", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "pattern", name="uq_banned_software_org_pattern"),
    )
    op.create_index(
        "ix_banned_software_org_id", "banned_software", ["org_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_banned_software_org_id", table_name="banned_software")
    op.drop_table("banned_software")
