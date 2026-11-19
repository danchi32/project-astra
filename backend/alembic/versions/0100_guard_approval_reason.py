"""Phase 3c · C3b: why a USB write request was made (a code from a fixed list).

Revision ID: 0100
Revises: 0099
"""
import sqlalchemy as sa

from alembic import op

revision = "0100"
down_revision = "0099"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("guard_approvals", sa.Column("reason", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("guard_approvals", "reason")
