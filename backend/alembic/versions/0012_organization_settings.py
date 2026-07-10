"""Organization settings

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-10
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organization_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("auto_approve_automatic", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("require_admin_for_approval_tier", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("min_password_length", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("enrollment_token_default_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("org_id", name="uq_organization_settings_org"),
    )
    op.create_index("ix_organization_settings_org_id", "organization_settings", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_organization_settings_org_id", table_name="organization_settings")
    op.drop_table("organization_settings")
