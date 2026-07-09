"""Knowledge base articles

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-09
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

source_enum = sa.Enum(
    "manual", "resolved_issue", name="knowledgesource", native_enum=False, length=20,
)


def upgrade() -> None:
    op.create_table(
        "knowledge_articles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("content", sa.String(20000), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("source", source_enum, nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_knowledge_articles_org_id", "knowledge_articles", ["org_id"])


def downgrade() -> None:
    op.drop_table("knowledge_articles")
