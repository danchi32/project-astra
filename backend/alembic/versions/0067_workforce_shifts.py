"""Workforce Insights ("Tracker") — department shifts.

Adds work_shifts (named per-org shifts with a timezone and local start/end, e.g. APAC / UK /
US / India General) and a nullable user_teams.shift_id assigning a shift to a team. SET NULL
on shift delete, so removing a shift un-assigns teams rather than deleting them.

Revision ID: 0067
Revises: 0066
"""
import sqlalchemy as sa
from alembic import op

from app.models.base import GUID

revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "work_shifts",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("org_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("start_minute", sa.Integer(), nullable=False),
        sa.Column("end_minute", sa.Integer(), nullable=False),
        sa.Column("working_days", sa.JSON(), nullable=False),
        sa.Column("colour", sa.String(length=9), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("org_id", "name", name="uq_work_shifts_org_name"),
    )
    op.add_column(
        "user_teams",
        sa.Column("shift_id", GUID(),
                  sa.ForeignKey("work_shifts.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_user_teams_shift_id", "user_teams", ["shift_id"])


def downgrade() -> None:
    op.drop_index("ix_user_teams_shift_id", table_name="user_teams")
    op.drop_column("user_teams", "shift_id")
    op.drop_table("work_shifts")
