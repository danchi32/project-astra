"""Phase 3 · D7: requests to let one sensitive paste / upload through, and the admin's answer.

Revision ID: 0090
Revises: 0089
"""
import sqlalchemy as sa

from alembic import op
from app.models.base import GUID

revision = "0090"
down_revision = "0089"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guard_approvals",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("org_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", GUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("windows_user", sa.String(256), nullable=False),
        sa.Column("site", sa.String(253), nullable=False),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("counts", sa.JSON(), nullable=False),
        sa.Column("contact_list", sa.Boolean(), nullable=False),
        sa.Column("keyword_hits", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by_user_id", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_guard_approvals_org_status", "guard_approvals", ["org_id", "status"])
    op.create_index("ix_guard_approvals_device_id", "guard_approvals", ["device_id"])


def downgrade() -> None:
    op.drop_index("ix_guard_approvals_device_id", table_name="guard_approvals")
    op.drop_index("ix_guard_approvals_org_status", table_name="guard_approvals")
    op.drop_table("guard_approvals")
