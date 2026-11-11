"""Software pushes (A2 + A4).

deployments: one push of one action to many devices; remediation_tasks.deployment_id ties
each device's task to it so the portal can show the push with a per-device status.

Revision ID: 0078
Revises: 0077
"""
import sqlalchemy as sa

from alembic import op
from app.models.base import GUID

revision = "0078"
down_revision = "0077"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deployments",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("org_id", GUID(), nullable=False),
        sa.Column("action_id", sa.String(length=50), nullable=False),
        sa.Column("params", sa.JSON(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column("created_by_user_id", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("targets", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_deployments_org_id", "deployments", ["org_id"])
    with op.batch_alter_table("remediation_tasks") as batch:
        batch.add_column(sa.Column("deployment_id", GUID(), nullable=True))
        batch.create_foreign_key("fk_remediation_tasks_deployment", "deployments",
                                 ["deployment_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_remediation_tasks_deployment_id", ["deployment_id"])


def downgrade() -> None:
    with op.batch_alter_table("remediation_tasks") as batch:
        batch.drop_index("ix_remediation_tasks_deployment_id")
        batch.drop_constraint("fk_remediation_tasks_deployment", type_="foreignkey")
        batch.drop_column("deployment_id")
    op.drop_index("ix_deployments_org_id", table_name="deployments")
    op.drop_table("deployments")
