"""Phase 3 · D1: the hosts of the site categories an org blocks, as saved.

Revision ID: 0094
Revises: 0093
"""
import sqlalchemy as sa

from alembic import op

revision = "0094"
down_revision = "0093"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("org_browser_policies",
                  sa.Column("category_hosts", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.alter_column("org_browser_policies", "category_hosts", server_default=None)


def downgrade() -> None:
    op.drop_column("org_browser_policies", "category_hosts")
