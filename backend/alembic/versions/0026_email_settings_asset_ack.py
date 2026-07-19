"""Per-org email sending identity + asset assignment acknowledgement

Revision ID: 0026
Revises: 0025
Create Date: 2026-07-19
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("method", sa.String(length=20), nullable=False, server_default="dns"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="unconfigured"),
        sa.Column("from_name", sa.String(length=120), nullable=True),
        sa.Column("from_address", sa.String(length=320), nullable=True),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("provider_domain_id", sa.String(length=100), nullable=True),
        sa.Column("dns_records", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_email_settings_org_id", "email_settings", ["org_id"], unique=True)

    op.add_column(
        "assets",
        sa.Column("acknowledgement_status", sa.String(length=20), nullable=False,
                  server_default="not_required"),
    )
    op.add_column("assets", sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("assets", sa.Column("ack_token", sa.String(length=64), nullable=True))
    op.create_index("ix_assets_ack_token", "assets", ["ack_token"])


def downgrade() -> None:
    op.drop_index("ix_assets_ack_token", table_name="assets")
    op.drop_column("assets", "ack_token")
    op.drop_column("assets", "acknowledged_at")
    op.drop_column("assets", "acknowledgement_status")
    op.drop_index("ix_email_settings_org_id", table_name="email_settings")
    op.drop_table("email_settings")
