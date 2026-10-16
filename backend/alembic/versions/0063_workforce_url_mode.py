"""Workforce Insights ("Tracker") — path-without-query URL mode.

Additive:
  * organizations.workforce_url_mode — "domain" (default) or "path". A per-org opt-in that
    records the page path as well as the host, with the query string always stripped.
  * activity_samples.path — the query-stripped path, set only in path mode.

Revision ID: 0063
Revises: 0062
"""
import sqlalchemy as sa
from alembic import op

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("workforce_url_mode", sa.String(length=10), nullable=False,
                  server_default="domain"),
    )
    op.add_column("activity_samples", sa.Column("path", sa.String(length=400), nullable=True))


def downgrade() -> None:
    op.drop_column("activity_samples", "path")
    op.drop_column("organizations", "workforce_url_mode")
