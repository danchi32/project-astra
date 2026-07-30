"""Per-update state and error code on device_windows_updates

is_installed is a boolean, and Windows has more than two answers. A device that had
installed its updates and only needed a reboot was stored exactly like one that had never
patched, and an update failing to download ("Download error - 0x80244018", offered a Retry
by Windows itself) was stored like one nobody had pushed yet. The portal could only ever
say "Pending", which is why it contradicted the device's own Windows Update page.

state carries what Windows shows; error_code carries the HRESULT, without which "failed"
cannot be triaged without walking to the machine.

Backfill maps the old boolean onto the two states it could actually express. Nothing is
guessed: a row that said installed becomes installed, and everything else becomes pending —
the same claim the row was already making. Real states arrive with the next collection from
an agent that knows how to report them.

Revision ID: 0037
Revises: 0036
Create Date: 2026-07-30
"""
import sqlalchemy as sa
from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Added nullable + server_default so the existing rows are valid the instant the column
    # exists; the backfill then sets real values and the column is made NOT NULL.
    op.add_column(
        "device_windows_updates",
        sa.Column("state", sa.String(length=20), nullable=True, server_default="pending"),
    )
    op.add_column(
        "device_windows_updates",
        sa.Column("error_code", sa.String(length=20), nullable=True),
    )
    op.execute(
        "UPDATE device_windows_updates "
        "SET state = CASE WHEN is_installed THEN 'installed' ELSE 'pending' END"
    )
    op.alter_column("device_windows_updates", "state", nullable=False)


def downgrade() -> None:
    # is_installed was never dropped, so going back loses only the finer states.
    op.drop_column("device_windows_updates", "error_code")
    op.drop_column("device_windows_updates", "state")
