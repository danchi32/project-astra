"""Workforce Insights ("Tracker") — productivity (P3): foreground samples + app usage.

Additive:
  * activity_samples gains `app` and `domain` (filled only for kind="foreground").
  * daily_app_usage: minutes per (device, account, day, app/site) with a productivity bucket —
    the breakdown behind the productive/neutral/unproductive split and the per-user detail view.

The daily_user_summary productive/neutral/unproductive/active columns already exist (0061);
this is what finally populates them. Still gated by the workforce_insights entitlement, so
these stay empty for every org that isn't tracked.

Revision ID: 0062
Revises: 0061
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("activity_samples", sa.Column("app", sa.String(length=260), nullable=True))
    op.add_column("activity_samples", sa.Column("domain", sa.String(length=255), nullable=True))

    op.create_table(
        "daily_app_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=150), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("label", sa.String(length=260), nullable=False),
        sa.Column("bucket", sa.String(length=20), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", "username", "day", "label",
                           name="uq_daily_app_usage_dev_user_day_label"),
    )
    op.create_index("ix_daily_app_usage_device_id", "daily_app_usage", ["device_id"])
    op.create_index("ix_daily_app_usage_org_id", "daily_app_usage", ["org_id"])
    op.create_index("ix_daily_app_usage_day", "daily_app_usage", ["day"])
    # The detail view reads one org's rows for one account over a day range.
    op.create_index(
        "ix_daily_app_usage_org_user_day", "daily_app_usage", ["org_id", "username", "day"]
    )


def downgrade() -> None:
    for name in (
        "ix_daily_app_usage_org_user_day",
        "ix_daily_app_usage_day",
        "ix_daily_app_usage_org_id",
        "ix_daily_app_usage_device_id",
    ):
        op.drop_index(name, table_name="daily_app_usage")
    op.drop_table("daily_app_usage")

    op.drop_column("activity_samples", "domain")
    op.drop_column("activity_samples", "app")
