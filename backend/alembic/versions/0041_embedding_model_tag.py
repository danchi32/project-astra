"""Record which embedding model produced each stored vector

Additive, and the backfill is the point. Every vector currently in these tables came from
the 256-dimension hashing provider, so they are all stamped "hash-256". Without that stamp,
configuring a real embedding provider would leave the old rows looking like same-space
vectors — and because cosine similarity returns 0.0 on a dimension mismatch instead of
raising, every one of them would quietly stop being retrievable with no error anywhere.

Revision ID: 0041
Revises: 0040
Create Date: 2026-08-06
"""
import sqlalchemy as sa
from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None

_TABLES = ("knowledge_articles", "semantic_cache_entries", "learned_actions")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "embedding_model",
                sa.String(length=60),
                nullable=False,
                server_default="hash-256",
            ),
        )
        # Search filters every read by this column, so it earns an index on all three.
        op.create_index(f"ix_{table}_embedding_model", table, ["embedding_model"])


def downgrade() -> None:
    for table in _TABLES:
        op.drop_index(f"ix_{table}_embedding_model", table_name=table)
        op.drop_column(table, "embedding_model")
