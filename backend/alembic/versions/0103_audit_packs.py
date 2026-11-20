"""Phase 3b · I4: a client's security questionnaire and SAVIO's draft answers.

Revision ID: 0103
Revises: 0102
"""
import sqlalchemy as sa

from alembic import op
from app.models.base import GUID

revision = "0103"
down_revision = "0102"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_packs",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("org_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("error", sa.String(300), nullable=True),
        sa.Column("rows", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_audit_packs_org_id", "audit_packs", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_packs_org_id", table_name="audit_packs")
    op.drop_table("audit_packs")
