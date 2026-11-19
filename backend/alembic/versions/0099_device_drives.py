"""Phase 3c · C3b: the USB drives each PC reports, so an admin can approve company drives.

Revision ID: 0099
Revises: 0098
"""
import sqlalchemy as sa

from alembic import op

revision = "0099"
down_revision = "0098"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("device_browser_policy_states",
                  sa.Column("drives", sa.JSON(), nullable=False, server_default="[]"))
    op.alter_column("device_browser_policy_states", "drives", server_default=None)


def downgrade() -> None:
    op.drop_column("device_browser_policy_states", "drives")
