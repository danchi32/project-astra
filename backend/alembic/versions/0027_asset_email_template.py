"""Org-customizable asset-assignment email template

Revision ID: 0027
Revises: 0026
Create Date: 2026-07-19
"""
import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("email_settings", sa.Column("asset_email_subject", sa.String(length=300), nullable=True))
    op.add_column("email_settings", sa.Column("asset_email_body", sa.String(length=4000), nullable=True))


def downgrade() -> None:
    op.drop_column("email_settings", "asset_email_body")
    op.drop_column("email_settings", "asset_email_subject")
