"""Record the tray version a device is actually running.

The tray updates on its own track from the elevated service, and until now it reported
nothing at all. A portal showing an up-to-date agent could therefore be sitting on a tray
several releases behind, and nobody could tell — the drift only surfaced when a user asked
for an action the tray had never heard of and got "not supported by the desktop agent".

Nullable, because every agent released before this one omits the field, and a device with no
tray installed has no version to report. The ingest writes it only when present, so an older
agent's silence never blanks a value a newer one recorded.

Revision ID: 0053
Revises: 0052
"""
import sqlalchemy as sa
from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("tray_version", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("devices", "tray_version")
