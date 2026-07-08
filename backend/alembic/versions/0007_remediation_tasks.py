"""Remediation tasks (self-healing)

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-08
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

status_enum = sa.Enum(
    "pending_approval", "approved", "dispatched", "succeeded", "failed", "rejected",
    name="remediationstatus", native_enum=False, length=20,
)
source_enum = sa.Enum(
    "assistant", "user", name="remediationsource", native_enum=False, length=20,
)


def upgrade() -> None:
    op.create_table(
        "remediation_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_id", sa.String(50), nullable=False),
        sa.Column("params", sa.JSON(), nullable=True),
        sa.Column("tier", sa.String(20), nullable=False),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("source", source_enum, nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_remediation_tasks_org_id", "remediation_tasks", ["org_id"])
    op.create_index("ix_remediation_tasks_device_id", "remediation_tasks", ["device_id"])
    op.create_index("ix_remediation_tasks_status", "remediation_tasks", ["status"])


def downgrade() -> None:
    op.drop_table("remediation_tasks")
