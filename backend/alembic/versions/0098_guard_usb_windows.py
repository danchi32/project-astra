"""Phase 3c · C3: USB write windows IT opens for one PC in "write on request" mode.

Revision ID: 0098
Revises: 0097
"""
import sqlalchemy as sa

from alembic import op
from app.models.base import GUID

revision = "0098"
down_revision = "0097"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guard_usb_windows",
        sa.Column("device_id", GUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("org_id", GUID(), nullable=False),
        sa.Column("until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opened_by_user_id", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_guard_usb_windows_org_id", "guard_usb_windows", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_guard_usb_windows_org_id", table_name="guard_usb_windows")
    op.drop_table("guard_usb_windows")
