"""Device BIOS version and release date.

Agent 0.14 sends serial, BIOS version and BIOS release date with the hourly hardware info.
The serial already has a column (filled at enrollment); this adds the other two. BIOS date is
the best age signal for a machine nobody recorded a purchase date for.

Revision ID: 0074
Revises: 0073
"""
import sqlalchemy as sa

from alembic import op

revision = "0074"
down_revision = "0073"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("devices") as batch:
        batch.add_column(sa.Column("bios_version", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("bios_release_date", sa.String(length=10), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("devices") as batch:
        batch.drop_column("bios_release_date")
        batch.drop_column("bios_version")
