"""Workforce Insights ("Tracker") — mouse-jiggler ("idle-faking") signal.

Additive:
  * activity_samples.idle_suspect — this foreground window's mouse input looked mechanically
    faked (a jiggler): confined movement, no clicks. Mouse-only, never the keyboard.
  * daily_user_summary.suspected_idle_minutes — the per-day roll-up of that signal, a flag
    for review, not a verdict.

Revision ID: 0064
Revises: 0063
"""
import sqlalchemy as sa
from alembic import op

revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "activity_samples",
        sa.Column("idle_suspect", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "daily_user_summary",
        sa.Column("suspected_idle_minutes", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("daily_user_summary", "suspected_idle_minutes")
    op.drop_column("activity_samples", "idle_suspect")
