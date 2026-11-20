"""Phase 3 · D7: the answer to a warn / justify prompt on a guard event, and its reason code.

Revision ID: 0089
Revises: 0088
"""
import sqlalchemy as sa

from alembic import op

revision = "0089"
down_revision = "0088"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("guard_events", sa.Column("outcome", sa.String(10), nullable=True))
    op.add_column("guard_events", sa.Column("reason", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("guard_events", "reason")
    op.drop_column("guard_events", "outcome")
