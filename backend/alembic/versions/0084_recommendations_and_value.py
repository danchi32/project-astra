"""J2 recommendations, and J5's two org settings (minutes per fix, IT hourly cost).

Revision ID: 0084
Revises: 0083
"""
import sqlalchemy as sa

from alembic import op
from app.models.base import GUID

revision = "0084"
down_revision = "0083"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recommendations",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("org_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("risk", sa.String(10), nullable=False),
        sa.Column("effort", sa.String(20), nullable=False),
        sa.Column("time_minutes", sa.Integer(), nullable=True),
        sa.Column("action_id", sa.String(50), nullable=True),
        sa.Column("advice", sa.String(600), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("dismissed_reason", sa.String(300), nullable=True),
        sa.Column("dismissed_by_user_id", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("org_id", "key", name="uq_recommendations_org_key"),
    )
    op.create_index("ix_recommendations_org_id", "recommendations", ["org_id"])
    op.add_column("organization_settings",
                  sa.Column("minutes_per_fix", sa.Integer(), nullable=False, server_default="15"))
    op.add_column("organization_settings", sa.Column("it_hourly_cost", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("organization_settings", "it_hourly_cost")
    op.drop_column("organization_settings", "minutes_per_fix")
    op.drop_index("ix_recommendations_org_id", table_name="recommendations")
    op.drop_table("recommendations")
