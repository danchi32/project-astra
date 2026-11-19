"""Phase 3b · I1: who handles privacy complaints and data breaches for the org.

Revision ID: 0101
Revises: 0100
"""
import sqlalchemy as sa

from alembic import op

revision = "0101"
down_revision = "0100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organization_settings", sa.Column("privacy_contact_name", sa.String(120), nullable=True))
    op.add_column("organization_settings", sa.Column("privacy_contact_email", sa.String(254), nullable=True))


def downgrade() -> None:
    op.drop_column("organization_settings", "privacy_contact_email")
    op.drop_column("organization_settings", "privacy_contact_name")
