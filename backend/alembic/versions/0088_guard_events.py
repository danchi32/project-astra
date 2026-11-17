"""Phase 3 · E3: what the browser extension saw on each PC (counts only).

Revision ID: 0088
Revises: 0087
"""
import sqlalchemy as sa

from alembic import op
from app.models.base import GUID

revision = "0088"
down_revision = "0087"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guard_events",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("org_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", GUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("windows_user", sa.String(256), nullable=False),
        sa.Column("site", sa.String(253), nullable=False),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("counts", sa.JSON(), nullable=False),
        sa.Column("contact_list", sa.Boolean(), nullable=False),
        sa.Column("keyword_hits", sa.Integer(), nullable=False),
        sa.Column("unknown", sa.Boolean(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_guard_events_org_occurred", "guard_events", ["org_id", "occurred_at"])
    op.create_index("ix_guard_events_device_id", "guard_events", ["device_id"])


def downgrade() -> None:
    op.drop_index("ix_guard_events_device_id", table_name="guard_events")
    op.drop_index("ix_guard_events_org_occurred", table_name="guard_events")
    op.drop_table("guard_events")
