"""Mark sales-demo organisations.

Additive: one boolean on `organizations`, false for every existing row. A demo tenant
holds an invented fleet; the flag keeps it out of the public homepage stats and the
revenue rollups, and is what the demo seed script checks before it deletes anything.

Revision ID: 0060
Revises: 0059
"""
import sqlalchemy as sa
from alembic import op

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("organizations", "is_demo")
