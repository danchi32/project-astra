"""Security posture per device (2a, Security Score).

Adds device_postures: Defender real-time protection and signature age, the three firewall
profiles, and BitLocker on the OS drive, as the agent reads them (0.15+). One row per device,
replaced on each report. Facts only; app.services.compliance decides pass / fail.

Revision ID: 0079
Revises: 0078
"""
import sqlalchemy as sa

from alembic import op
from app.models.base import GUID

revision = "0079"
down_revision = "0078"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_postures",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("device_id", GUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("org_id", GUID(), nullable=False),
        sa.Column("defender_realtime", sa.Boolean(), nullable=True),
        sa.Column("defender_signature_age_days", sa.Integer(), nullable=True),
        sa.Column("firewall_domain", sa.Boolean(), nullable=True),
        sa.Column("firewall_private", sa.Boolean(), nullable=True),
        sa.Column("firewall_public", sa.Boolean(), nullable=True),
        sa.Column("bitlocker_os_drive", sa.Boolean(), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_device_postures_org_id", "device_postures", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_device_postures_org_id", table_name="device_postures")
    op.drop_table("device_postures")
