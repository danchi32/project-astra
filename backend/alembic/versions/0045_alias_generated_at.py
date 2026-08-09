"""knowledge_articles.aliases_generated_at: say whether the aliases were ever written

Query aliases are what make an article findable by the words a user actually types. When
the model is unreachable the article still saves — correctly — but with no aliases, and
retrieval then only matches the article's own wording: a user typing "wifi" scores exactly
0.0 against "Wi-Fi keeps dropping" and the search returns nothing at all.

Nothing could find those articles afterwards to fix them. `symptom_samples IS NULL` looks
like it would work and does not: SQLAlchemy writes a Python None into a JSON column as the
JSON value 'null', which is not SQL NULL, so the query matches zero rows while the Python
side reads back None. An explicit timestamp column has no such ambiguity, and it also
records when the aliases were written.

Backfills existing rows: a row that already holds a non-empty alias list plainly had them
generated, so it is stamped with its creation time rather than being queued for a
regeneration that would cost an LLM call and change nothing.

Revision ID: 0045
Revises: 0044
"""
import sqlalchemy as sa
from alembic import op

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "knowledge_articles",
        sa.Column("aliases_generated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_knowledge_articles_aliases_generated_at",
        "knowledge_articles",
        ["aliases_generated_at"],
    )
    # Rows that already have aliases are done. Everything else stays NULL and will be
    # picked up by scripts/backfill_aliases.py.
    op.execute(
        """
        UPDATE knowledge_articles
           SET aliases_generated_at = created_at
         WHERE symptom_samples IS NOT NULL
           AND symptom_samples::text NOT IN ('null', '[]')
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_knowledge_articles_aliases_generated_at", table_name="knowledge_articles"
    )
    op.drop_column("knowledge_articles", "aliases_generated_at")
