"""Local Windows accounts per device (A1).

device_local_accounts: who can sign in to a PC and who is a local administrator, reported by
agent 0.14+ with the hourly inventory and replaced as a set. Backs the device page's Users
tab (enable/disable, make admin / standard user, new user).

Revision ID: 0077
Revises: 0076
"""
import sqlalchemy as sa

from alembic import op
from app.models.base import GUID

revision = "0077"
down_revision = "0076"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_local_accounts",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("device_id", GUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("org_id", GUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("built_in", sa.Boolean(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_device_local_accounts_device_id", "device_local_accounts", ["device_id"])
    op.create_index("ix_device_local_accounts_org_id", "device_local_accounts", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_device_local_accounts_org_id", table_name="device_local_accounts")
    op.drop_index("ix_device_local_accounts_device_id", table_name="device_local_accounts")
    op.drop_table("device_local_accounts")
