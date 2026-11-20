"""Phase 3c · C1: AI Guard cases (one story per person, not one alert per event) and quiet sites.

Revision ID: 0096
Revises: 0095
"""
import sqlalchemy as sa

from alembic import op
from app.models.base import GUID

revision = "0096"
down_revision = "0095"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guard_cases",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("org_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("windows_user", sa.String(256), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("resolution", sa.String(10), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(10), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by_user_id", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_guard_cases_org_status", "guard_cases", ["org_id", "status"])
    op.create_table(
        "guard_quiet_sites",
        sa.Column("org_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("site", sa.String(253), primary_key=True),
        sa.Column("created_by_user_id", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("guard_quiet_sites")
    op.drop_index("ix_guard_cases_org_status", table_name="guard_cases")
    op.drop_table("guard_cases")
