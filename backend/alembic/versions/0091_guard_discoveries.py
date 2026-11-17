"""Phase 3 · D5: each PC's latest map of where sensitive files are (folder counts only).

Revision ID: 0091
Revises: 0090
"""
import sqlalchemy as sa

from alembic import op
from app.models.base import GUID

revision = "0091"
down_revision = "0090"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guard_discoveries",
        sa.Column("device_id", GUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("org_id", GUID(), nullable=False),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("files_scanned", sa.Integer(), nullable=False),
        sa.Column("files_skipped", sa.Integer(), nullable=False),
        sa.Column("truncated", sa.Boolean(), nullable=False),
        sa.Column("folders", sa.JSON(), nullable=False),
    )
    op.create_index("ix_guard_discoveries_org_id", "guard_discoveries", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_guard_discoveries_org_id", table_name="guard_discoveries")
    op.drop_table("guard_discoveries")
