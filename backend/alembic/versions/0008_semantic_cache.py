"""Semantic cache for AI answers

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-09
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "semantic_cache_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query_text", sa.String(1000), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("answer", sa.String(10000), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_semantic_cache_entries_org_id", "semantic_cache_entries", ["org_id"])


def downgrade() -> None:
    op.drop_table("semantic_cache_entries")
