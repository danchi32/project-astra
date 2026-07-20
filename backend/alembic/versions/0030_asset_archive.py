"""Soft-delete (archive) for assets

Revision ID: 0030
Revises: 0029
Create Date: 2026-07-20
"""
import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_assets_archived_at", "assets", ["archived_at"])


def downgrade() -> None:
    op.drop_index("ix_assets_archived_at", table_name="assets")
    op.drop_column("assets", "archived_at")
