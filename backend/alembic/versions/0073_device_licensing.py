"""Windows / Office activation per device.

Adds device_licensing: the products the Software Protection Platform reports as holding a
key (agent 0.14+, hourly). Facts only; app.services.licensing decides "activated" and
"cracked", so its signature list can change without a migration.

Revision ID: 0073
Revises: 0072
"""
import sqlalchemy as sa

from alembic import op
from app.models.base import GUID

revision = "0073"
down_revision = "0072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_licensing",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("device_id", GUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("org_id", GUID(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=True),
        sa.Column("license_status", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=50), nullable=True),
        sa.Column("kms_host", sa.String(length=255), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_device_licensing_device_id", "device_licensing", ["device_id"])
    op.create_index("ix_device_licensing_org_id", "device_licensing", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_device_licensing_org_id", table_name="device_licensing")
    op.drop_index("ix_device_licensing_device_id", table_name="device_licensing")
    op.drop_table("device_licensing")
