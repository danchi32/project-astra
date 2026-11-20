"""Signup collects a phone number: kept on the organisation, and on the pending signup
while its email code is outstanding.

Both nullable. Organisations created before this have no number, and inventing one would
be worse than the gap; the signup schema is what makes it required for new ones.

Revision "0086a", not "0087": phase-3 already owns 0087 onwards. Whichever of the two
lands on main second re-points its first migration at the other's head.

Revision ID: 0086a
Revises: 0086
"""
import sqlalchemy as sa

from alembic import op

revision = "0086a"
down_revision = "0086"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("contact_phone", sa.String(16), nullable=True))
    op.add_column("pending_registrations", sa.Column("phone", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("pending_registrations", "phone")
    op.drop_column("organizations", "contact_phone")
