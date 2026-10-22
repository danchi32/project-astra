"""Workforce Insights ("Tracker") — per-org productivity reclassification.

Additive: organizations.workforce_categories — a JSON map letting a customer override which
apps/domains count as productive / neutral / unproductive, on top of the built-in taxonomy.
Null for every existing org (the default taxonomy is the answer); an override only flips the
bucket, never the built-in label.

Revision ID: 0066
Revises: 0065
"""
import sqlalchemy as sa
from alembic import op

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("workforce_categories", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("organizations", "workforce_categories")
