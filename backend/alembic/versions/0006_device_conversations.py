"""Allow device-owned conversations (tray chat)

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-08
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("conversations") as batch:
        batch.alter_column("user_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
        batch.add_column(sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=True))
        batch.create_foreign_key(
            "fk_conversations_device_id", "devices", ["device_id"], ["id"], ondelete="CASCADE"
        )
    op.create_index("ix_conversations_device_id", "conversations", ["device_id"])


def downgrade() -> None:
    op.drop_index("ix_conversations_device_id", table_name="conversations")
    with op.batch_alter_table("conversations") as batch:
        batch.drop_constraint("fk_conversations_device_id", type_="foreignkey")
        batch.drop_column("device_id")
        batch.alter_column("user_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
