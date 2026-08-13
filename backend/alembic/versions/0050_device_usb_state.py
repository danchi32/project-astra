"""Record whether USB storage is blocked on each device.

The agent reads the actual registry state on every heartbeat, so this reflects reality
rather than what ASTRA last asked for — a port reopened by hand or by Group Policy shows as
allowed here. Nullable, and existing rows stay NULL until an agent new enough to report it
checks in: the compliance count reads NULL as "unknown", which is the honest answer for a
device nothing has yet looked at.

Revision ID: 0050
Revises: 0049
"""
import sqlalchemy as sa
from alembic import op

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column("usb_storage_blocked", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("devices", "usb_storage_blocked")
