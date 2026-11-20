"""Phase 3b · I1: breach records — what happened, whose data, and the steps taken.

Revision ID: 0102
Revises: 0101
"""
import sqlalchemy as sa

from alembic import op
from app.models.base import GUID

revision = "0102"
down_revision = "0101"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guard_incidents",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("org_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_id", GUID(), sa.ForeignKey("guard_cases.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("what_happened", sa.String(4000), nullable=False),
        sa.Column("found_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kinds", sa.JSON(), nullable=False),
        sa.Column("people_affected", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("opened_by_user_id", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_guard_incidents_org_status", "guard_incidents", ["org_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_guard_incidents_org_status", table_name="guard_incidents")
    op.drop_table("guard_incidents")
