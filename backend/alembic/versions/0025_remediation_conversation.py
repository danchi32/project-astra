"""Link a remediation task to the chat that proposed it (post result back)

Revision ID: 0025
Revises: 0024
Create Date: 2026-07-17
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "remediation_tasks",
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_remediation_tasks_conversation_id", "remediation_tasks", ["conversation_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_remediation_tasks_conversation_id", table_name="remediation_tasks")
    op.drop_column("remediation_tasks", "conversation_id")
