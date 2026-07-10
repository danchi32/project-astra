"""Notification center

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-10
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

category_enum = sa.Enum(
    "remediation", "telemetry", "asset", "system",
    name="notificationcategory", native_enum=False, length=20,
)
severity_enum = sa.Enum(
    "info", "warning", "critical",
    name="notificationseverity", native_enum=False, length=20,
)


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", category_enum, nullable=False),
        sa.Column("severity", severity_enum, nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.String(1000), nullable=False),
        sa.Column("link", sa.String(300), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notifications_org_id", "notifications", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_notifications_org_id", table_name="notifications")
    op.drop_table("notifications")
