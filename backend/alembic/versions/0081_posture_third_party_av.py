"""Security posture: whether another antivirus is registered (2a+ review fix).

With a third-party antivirus active, Defender's real-time protection is off by design, and the
Defender check must not fail the PC for it.

Revision ID: 0081
Revises: 0080
"""
import sqlalchemy as sa

from alembic import op

revision = "0081"
down_revision = "0080"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("device_postures", sa.Column("third_party_antivirus", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("device_postures", "third_party_antivirus")
