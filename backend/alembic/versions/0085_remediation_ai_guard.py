"""C3 review fix: SAVIO's hold reasons get their own column on remediation tasks.

They were appended to the model-written `reason`, where the model could forge a look-alike.

Revision ID: 0085
Revises: 0084
"""
import sqlalchemy as sa

from alembic import op

revision = "0085"
down_revision = "0084"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("remediation_tasks", sa.Column("ai_guard", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("remediation_tasks", "ai_guard")
