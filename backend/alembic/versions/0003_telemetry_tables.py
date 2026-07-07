"""Telemetry tables: snapshots, event logs, installed apps, services, updates

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-07
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telemetry_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("device_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cpu_percent", sa.Float(), nullable=False),
        sa.Column("ram_total_mb", sa.Integer(), nullable=False),
        sa.Column("ram_used_mb", sa.Integer(), nullable=False),
        sa.Column("disks", sa.JSON(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_telemetry_snapshots_device_id", "telemetry_snapshots", ["device_id"])
    op.create_index("ix_telemetry_snapshots_org_id", "telemetry_snapshots", ["org_id"])

    op.create_table(
        "device_event_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("device_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("log_name", sa.String(100), nullable=False),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("message", sa.String(2000), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_device_event_logs_device_id", "device_event_logs", ["device_id"])
    op.create_index("ix_device_event_logs_org_id", "device_event_logs", ["org_id"])

    op.create_table(
        "device_installed_apps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("device_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("version", sa.String(100), nullable=True),
        sa.Column("publisher", sa.String(200), nullable=True),
        sa.Column("install_date", sa.String(20), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_device_installed_apps_device_id", "device_installed_apps", ["device_id"])
    op.create_index("ix_device_installed_apps_org_id", "device_installed_apps", ["org_id"])

    op.create_table(
        "device_services",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("device_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(300), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("start_type", sa.String(30), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_device_services_device_id", "device_services", ["device_id"])
    op.create_index("ix_device_services_org_id", "device_services", ["org_id"])

    op.create_table(
        "device_windows_updates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("device_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kb_article_id", sa.String(30), nullable=False),
        sa.Column("title", sa.String(400), nullable=False),
        sa.Column("is_installed", sa.Boolean(), nullable=False),
        sa.Column("installed_on", sa.String(30), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_device_windows_updates_device_id", "device_windows_updates", ["device_id"])
    op.create_index("ix_device_windows_updates_org_id", "device_windows_updates", ["org_id"])


def downgrade() -> None:
    op.drop_table("device_windows_updates")
    op.drop_table("device_services")
    op.drop_table("device_installed_apps")
    op.drop_table("device_event_logs")
    op.drop_table("telemetry_snapshots")
