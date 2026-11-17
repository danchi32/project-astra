"""L5b: where an asset's warranty date came from, and a found date waiting for a choice.

Existing dates get no source: they were typed by a person, and `warranty.is_persons` treats
a dated asset with no source as a person's, so no lookup overwrites them.

Revision ID: 0086
Revises: 0085
"""
import sqlalchemy as sa

from alembic import op

revision = "0086"
down_revision = "0085"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("warranty_source", sa.String(20), nullable=True))
    op.add_column("assets", sa.Column("warranty_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("assets", sa.Column("warranty_found", sa.String(10), nullable=True))
    op.add_column("assets", sa.Column("warranty_found_source", sa.String(20), nullable=True))


def downgrade() -> None:
    for col in ("warranty_found_source", "warranty_found", "warranty_checked_at", "warranty_source"):
        op.drop_column("assets", col)
