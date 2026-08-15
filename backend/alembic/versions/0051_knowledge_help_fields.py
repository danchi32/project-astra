"""Let a global knowledge article also serve as a customer-facing help article.

Two nullable columns, both meaningful only on global articles (org_id NULL): the category
a customer browses by, and the error code they can see on their own screen. Existing rows
stay NULL, which is correct — an organization's own runbooks are not ASTRA support
documentation and must not appear in the help centre.

Publishing is not added here. `published_at` already exists and already gates what search
returns, so reusing it means unpublishing an article removes it from the help centre and
from the assistant's answers together, rather than leaving one of them stale.

Revision ID: 0051
Revises: 0050
"""
import sqlalchemy as sa
from alembic import op

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "knowledge_articles",
        sa.Column("help_category", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "knowledge_articles",
        sa.Column("error_code", sa.String(length=40), nullable=True),
    )
    # Both are lookup paths — browsing by category and jumping straight from a code.
    op.create_index(
        "ix_knowledge_articles_help_category", "knowledge_articles", ["help_category"]
    )
    op.create_index(
        "ix_knowledge_articles_error_code", "knowledge_articles", ["error_code"]
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_articles_error_code", table_name="knowledge_articles")
    op.drop_index("ix_knowledge_articles_help_category", table_name="knowledge_articles")
    op.drop_column("knowledge_articles", "error_code")
    op.drop_column("knowledge_articles", "help_category")
