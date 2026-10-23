"""Workforce Insights ("Tracker") — AI-learned productivity categories (global).

Adds learned_categories: apps/domains the built-in taxonomy didn't know, categorised once by
the AI and kept GLOBALLY so every org reuses them (re-entries and subdomains included) without
another AI call. One row per (kind, key); never touches the built-in defaults. A per-org
disagreement is a bucket override on that org, which outranks this.

Revision ID: 0071
Revises: 0070
"""
import sqlalchemy as sa
from alembic import op

from app.models.base import GUID

revision = "0071"
down_revision = "0070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learned_categories",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("key", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("source", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("kind", "key", name="uq_learned_categories_kind_key"),
    )


def downgrade() -> None:
    op.drop_table("learned_categories")
