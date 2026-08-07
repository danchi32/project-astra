"""Per-organization connection to the helpdesk they already run

Additive. Nothing here is global — every organization brings its own instance, its own
credential and its own category tree, which is why this is a table rather than settings on
the platform.

api_key_encrypted holds Fernet ciphertext, never a key. The credential it protects can read
every ticket and contact in a customer's service desk, so one database dump must not be
enough to use it.

Revision ID: 0043
Revises: 0042
Create Date: 2026-08-07
"""
import sqlalchemy as sa
from alembic import op

from app.models.base import GUID

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "helpdesk_settings",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("org_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, unique=True, index=True),
        sa.Column("provider", sa.String(length=30), nullable=False,
                  server_default="freshservice"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("domain", sa.String(length=120), nullable=True),
        sa.Column("api_key_encrypted", sa.String(length=500), nullable=True),
        sa.Column("default_priority", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("default_source", sa.Integer(), nullable=True),
        sa.Column("workspace_id", sa.Integer(), nullable=True),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column("category_map", sa.JSON(), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("helpdesk_settings")
