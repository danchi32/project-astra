"""Allow global knowledge articles (org_id NULL = shared with every org)

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-14
"""
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "knowledge_articles", "org_id",
        existing_type=postgresql.UUID(as_uuid=True), nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "knowledge_articles", "org_id",
        existing_type=postgresql.UUID(as_uuid=True), nullable=False,
    )
