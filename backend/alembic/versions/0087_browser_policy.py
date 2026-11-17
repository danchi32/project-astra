"""Phase 3 · D10: per-org browser policy and each device's last apply report.

Revision ID: 0087
Revises: 0086
"""
import sqlalchemy as sa

from alembic import op
from app.models.base import GUID

revision = "0087"
down_revision = "0086"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "org_browser_policies",
        sa.Column("org_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("policy", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_by_user_id", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "device_browser_policy_states",
        sa.Column("device_id", GUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("org_id", GUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_device_browser_policy_states_org_id", "device_browser_policy_states", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_device_browser_policy_states_org_id", table_name="device_browser_policy_states")
    op.drop_table("device_browser_policy_states")
    op.drop_table("org_browser_policies")
