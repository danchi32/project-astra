"""Phase 3 · D5: AI Guard policy suggestions an admin chose not to take.

Revision ID: 0092
Revises: 0091
"""
import sqlalchemy as sa

from alembic import op
from app.models.base import GUID

revision = "0092"
down_revision = "0091"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guard_suggestion_dismissals",
        sa.Column("org_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("key", sa.String(40), primary_key=True),
        sa.Column("dismissed_by_user_id", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("guard_suggestion_dismissals")
