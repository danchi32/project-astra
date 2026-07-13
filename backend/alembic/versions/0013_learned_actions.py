"""Learned actions — fixes the AI applied, reused for free on similar issues

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-11
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learned_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query_text", sa.String(1000), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("action_id", sa.String(64), nullable=False),
        sa.Column("params", sa.JSON(), nullable=True),
        sa.Column("hit_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_learned_actions_org_id", "learned_actions", ["org_id"])


def downgrade() -> None:
    op.drop_table("learned_actions")
