"""Workforce Insights ("Tracker") — attendance configuration.

Adds organizations.workforce_attendance (JSON: working_days + full/half-day thresholds) and a
work_holidays table (named non-working dates per org). Both feed the attendance register so it
stops assuming Mon–Fri with no holidays.

Revision ID: 0069
Revises: 0068
"""
import sqlalchemy as sa
from alembic import op

from app.models.base import GUID

revision = "0069"
down_revision = "0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("workforce_attendance", sa.JSON(), nullable=True),
    )
    op.create_table(
        "work_holidays",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("org_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("org_id", "day", name="uq_work_holidays_org_day"),
    )


def downgrade() -> None:
    op.drop_table("work_holidays")
    op.drop_column("organizations", "workforce_attendance")
