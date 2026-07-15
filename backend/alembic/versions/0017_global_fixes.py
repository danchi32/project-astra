"""Allow global learned-action fixes (org_id NULL = auto-applies for every org)

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-14
"""
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "learned_actions", "org_id",
        existing_type=postgresql.UUID(as_uuid=True), nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "learned_actions", "org_id",
        existing_type=postgresql.UUID(as_uuid=True), nullable=False,
    )
