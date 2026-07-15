"""Invite codes — gate that makes organization creation invite-only

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-14
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invite_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_by_org_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_invite_codes_code_hash", "invite_codes", ["code_hash"], unique=True)


def downgrade() -> None:
    op.drop_table("invite_codes")
