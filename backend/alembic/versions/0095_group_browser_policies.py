"""Phase 3 · D1: a device group's own browser policy, and one version sequence per org.

Revision ID: 0095
Revises: 0094
"""
import sqlalchemy as sa

from alembic import op
from app.models.base import GUID

revision = "0095"
down_revision = "0094"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Every version issued so far belongs to the org's one policy, so the sequence starts there.
    op.add_column("org_browser_policies", sa.Column("seq", sa.Integer(), nullable=False, server_default="1"))
    op.execute("UPDATE org_browser_policies SET seq = version")
    op.alter_column("org_browser_policies", "seq", server_default=None)
    op.create_table(
        "group_browser_policies",
        sa.Column("group_id", GUID(), sa.ForeignKey("device_groups.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("org_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("policy", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("category_hosts", sa.JSON(), nullable=False),
        sa.Column("updated_by_user_id", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_group_browser_policies_org_id", "group_browser_policies", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_group_browser_policies_org_id", table_name="group_browser_policies")
    op.drop_table("group_browser_policies")
    op.drop_column("org_browser_policies", "seq")
