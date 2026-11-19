"""Phase 3c · C2: where an uploaded file was downloaded from (a host name), on each event.

Revision ID: 0097
Revises: 0096
"""
import sqlalchemy as sa

from alembic import op

revision = "0097"
down_revision = "0096"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("guard_events", sa.Column("origin", sa.String(253), nullable=True))


def downgrade() -> None:
    op.drop_column("guard_events", "origin")
