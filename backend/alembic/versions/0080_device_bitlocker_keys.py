"""BitLocker recovery keys escrowed from devices (2a+).

Adds device_bitlocker_keys. The recovery password is stored encrypted with the platform key
(app.core.crypto); the column never holds the plain value.

Revision ID: 0080
Revises: 0079
"""
import sqlalchemy as sa

from alembic import op
from app.models.base import GUID

revision = "0080"
down_revision = "0079"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_bitlocker_keys",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("device_id", GUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("org_id", GUID(), nullable=False),
        sa.Column("drive", sa.String(length=2), nullable=False),
        sa.Column("protector_id", sa.String(length=60), nullable=False),
        sa.Column("recovery_password_enc", sa.Text(), nullable=False),
        sa.Column("escrowed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("device_id", "drive", "protector_id", name="uq_device_bitlocker_key"),
    )
    op.create_index("ix_device_bitlocker_keys_device_id", "device_bitlocker_keys", ["device_id"])
    op.create_index("ix_device_bitlocker_keys_org_id", "device_bitlocker_keys", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_device_bitlocker_keys_org_id", table_name="device_bitlocker_keys")
    op.drop_index("ix_device_bitlocker_keys_device_id", table_name="device_bitlocker_keys")
    op.drop_table("device_bitlocker_keys")
