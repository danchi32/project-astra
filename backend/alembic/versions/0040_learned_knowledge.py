"""Knowledge articles that the platform learns from confirmed fixes

Additive columns on knowledge_articles. Everything already in the table is a
hand-written article, so the backfill publishes all of it — a migration that
quietly made existing runbooks unsearchable would be a far worse outcome than
one that publishes a candidate too eagerly.

Revision ID: 0040
Revises: 0039
Create Date: 2026-08-03
"""
import sqlalchemy as sa
from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_articles", sa.Column("action_id", sa.String(length=50), nullable=True))
    op.add_column("knowledge_articles", sa.Column("symptom_samples", sa.JSON(), nullable=True))
    op.add_column(
        "knowledge_articles",
        sa.Column("successes", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "knowledge_articles",
        sa.Column("failures", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "knowledge_articles",
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Every existing row predates learning and was written by a person — keep it searchable.
    op.execute(
        "UPDATE knowledge_articles SET published_at = created_at WHERE published_at IS NULL"
    )

    # Learning looks up "this org's candidate for this action" on every confirmed fix, which
    # is the one query that runs on the agent's hot path.
    op.create_index(
        "ix_knowledge_articles_org_action", "knowledge_articles", ["org_id", "action_id"]
    )
    op.create_index(
        "ix_knowledge_articles_published", "knowledge_articles", ["published_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_articles_published", table_name="knowledge_articles")
    op.drop_index("ix_knowledge_articles_org_action", table_name="knowledge_articles")
    op.drop_column("knowledge_articles", "published_at")
    op.drop_column("knowledge_articles", "failures")
    op.drop_column("knowledge_articles", "successes")
    op.drop_column("knowledge_articles", "symptom_samples")
    op.drop_column("knowledge_articles", "action_id")
