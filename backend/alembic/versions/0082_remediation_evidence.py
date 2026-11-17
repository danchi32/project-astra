"""Proof-of-Fix (C1): before / after / 7-day recheck evidence on a remediation task.

Revision ID: 0082
Revises: 0081
"""
import sqlalchemy as sa

from alembic import op

revision = "0082"
down_revision = "0081"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("remediation_tasks", sa.Column("evidence", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("remediation_tasks", "evidence")
