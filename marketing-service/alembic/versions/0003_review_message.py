"""remember which Telegram message is asking about which item

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-29

Telegram hands a reply the id of the message it answers and nothing else. Without this,
"make it more concrete" arrives with no way to tell what it is about.
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("content_items", sa.Column("review_message_id", sa.BigInteger(), nullable=True))
    op.add_column("content_items", sa.Column("review_chat_id", sa.String(length=64), nullable=True))
    # Looked up on every inbound reply, so it is indexed rather than scanned.
    op.create_index(
        "ix_content_items_review_message", "content_items", ["review_message_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_content_items_review_message", table_name="content_items")
    op.drop_column("content_items", "review_chat_id")
    op.drop_column("content_items", "review_message_id")
