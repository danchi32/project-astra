"""Phase 3 · E8: a new org's AI Guard records only for its first 14 days.

Existing policies get no pilot (NULL): they were set up before it existed.

Revision ID: 0093
Revises: 0092
"""
import sqlalchemy as sa

from alembic import op

revision = "0093"
down_revision = "0092"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("org_browser_policies", sa.Column("pilot_until", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("org_browser_policies", "pilot_until")
