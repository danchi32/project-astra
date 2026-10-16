"""Workforce Insights ("Tracker") — attendance tables.

Three additive tables, no changes to anything that exists:

    activity_samples    raw presence events the agent pushes (retention-limited, pruned
                        per device on ingest like telemetry snapshots)
    work_sessions       derived "signed in and present" spans, one per (device, account, day)
    daily_user_summary  the durable per-(device, account, day) attendance headline

Keyed on the Windows account the agent already reports, not on a portal user; see
app/models/workforce.py and docs/WORKFORCE_INSIGHTS_PLAN.md. The feature is gated by the
`workforce_insights` entitlement (off until an operator grants it per org), so these tables
stay empty for every existing organisation until that switch and an agent that reports
activity both exist.

Revision ID: 0061
Revises: 0060
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activity_samples",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=150), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_activity_samples_device_id", "activity_samples", ["device_id"])
    op.create_index("ix_activity_samples_org_id", "activity_samples", ["org_id"])
    op.create_index("ix_activity_samples_occurred_at", "activity_samples", ["occurred_at"])
    # Aggregation reads one device's samples for a day, ordered by time. Pruning and that
    # read both filter device then time, so the pair is indexed together.
    op.create_index(
        "ix_activity_samples_device_occurred",
        "activity_samples",
        ["device_id", "occurred_at"],
    )

    op.create_table(
        "work_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=150), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_work_sessions_device_id", "work_sessions", ["device_id"])
    op.create_index("ix_work_sessions_org_id", "work_sessions", ["org_id"])
    op.create_index("ix_work_sessions_day", "work_sessions", ["day"])
    op.create_index(
        "ix_work_sessions_device_day", "work_sessions", ["device_id", "day"]
    )

    op.create_table(
        "daily_user_summary",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=150), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("first_in", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_out", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worked_minutes", sa.Integer(), nullable=False),
        sa.Column("active_minutes", sa.Integer(), nullable=True),
        sa.Column("idle_minutes", sa.Integer(), nullable=True),
        sa.Column("productive_minutes", sa.Integer(), nullable=True),
        sa.Column("neutral_minutes", sa.Integer(), nullable=True),
        sa.Column("unproductive_minutes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "device_id", "username", "day", name="uq_daily_user_summary_dev_user_day"
        ),
    )
    op.create_index("ix_daily_user_summary_device_id", "daily_user_summary", ["device_id"])
    op.create_index("ix_daily_user_summary_org_id", "daily_user_summary", ["org_id"])
    op.create_index("ix_daily_user_summary_user_id", "daily_user_summary", ["user_id"])
    op.create_index("ix_daily_user_summary_day", "daily_user_summary", ["day"])
    # The org attendance view is "this org, this day range". org + day is on every read.
    op.create_index(
        "ix_daily_user_summary_org_day", "daily_user_summary", ["org_id", "day"]
    )


def downgrade() -> None:
    for name in (
        "ix_daily_user_summary_org_day",
        "ix_daily_user_summary_day",
        "ix_daily_user_summary_user_id",
        "ix_daily_user_summary_org_id",
        "ix_daily_user_summary_device_id",
    ):
        op.drop_index(name, table_name="daily_user_summary")
    op.drop_table("daily_user_summary")

    for name in (
        "ix_work_sessions_device_day",
        "ix_work_sessions_day",
        "ix_work_sessions_org_id",
        "ix_work_sessions_device_id",
    ):
        op.drop_index(name, table_name="work_sessions")
    op.drop_table("work_sessions")

    for name in (
        "ix_activity_samples_device_occurred",
        "ix_activity_samples_occurred_at",
        "ix_activity_samples_org_id",
        "ix_activity_samples_device_id",
    ):
        op.drop_index(name, table_name="activity_samples")
    op.drop_table("activity_samples")
