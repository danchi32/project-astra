"""Workforce Insights ("Tracker") — real idle (P2: GetLastInputInfo active-vs-idle).

Additive: activity_samples.idle — no keyboard/mouse input past the threshold during this
foreground window, so it is a break rather than at-keyboard time. daily_user_summary already
carries active_minutes/idle_minutes (0061); this is what finally splits them.

Revision ID: 0065
Revises: 0064
"""
import sqlalchemy as sa
from alembic import op

revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "activity_samples",
        sa.Column("idle", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("activity_samples", "idle")
