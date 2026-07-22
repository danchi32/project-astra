"""Per-org Pro-AI entitlement (real Claude access)

Revision ID: 0031
Revises: 0030
Create Date: 2026-07-21
"""
import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("ai_pro", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("organizations", "ai_pro")
