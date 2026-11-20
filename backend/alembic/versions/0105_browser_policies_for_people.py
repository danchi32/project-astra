"""Browser policies follow people: named policies assigned to user teams and users, replacing
policies on device groups. A named policy is a full policy or an exception laid over one. A PC
gets the policies of the user it is assigned to in Assets.

Each existing group policy is kept as a named policy (the group's name) with nobody assigned,
so its settings are not lost; an admin assigns it to teams or users.

Revision ID: 0105
Revises: 0104
"""
import uuid

import sqlalchemy as sa

from alembic import op
from app.models.base import GUID

revision = "0105"
down_revision = "0104"
branch_labels = None
depends_on = None


def upgrade() -> None:
    table = op.create_table(
        "browser_policies",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("org_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False, server_default="full"),
        sa.Column("team_ids", sa.JSON(), nullable=False),
        sa.Column("user_ids", sa.JSON(), nullable=False),
        sa.Column("policy", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("category_hosts", sa.JSON(), nullable=False),
        sa.Column("allowed_category_hosts", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("updated_by_user_id", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("org_id", "name", name="uq_browser_policies_org_name"),
    )
    # Categories can be allowed too, not only blocked: their hosts are copied on save, as blocked ones are.
    op.add_column("org_browser_policies",
                  sa.Column("allowed_category_hosts", sa.JSON(), nullable=False, server_default="[]"))
    op.create_index("ix_browser_policies_org_id", "browser_policies", ["org_id"])
    old = op.get_bind().execute(sa.text(
        "SELECT d.name, g.org_id, g.priority, g.policy, g.version, g.category_hosts, g.updated_by_user_id,"
        " g.updated_at, g.created_at FROM group_browser_policies g JOIN device_groups d ON d.id = g.group_id"
    )).mappings().all()
    if old:
        op.bulk_insert(table, [{**r, "id": uuid.uuid4(), "kind": "full", "team_ids": [], "user_ids": [],
                                    "allowed_category_hosts": []} for r in old])
    op.drop_index("ix_group_browser_policies_org_id", table_name="group_browser_policies")
    op.drop_table("group_browser_policies")


def downgrade() -> None:
    # Named policies cannot be put back on device groups: they come back empty.
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
    op.drop_index("ix_browser_policies_org_id", table_name="browser_policies")
    op.drop_table("browser_policies")
    op.drop_column("org_browser_policies", "allowed_category_hosts")
