"""the line that goes on the image

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-29

A card carrying a sentence makes the same claim a paragraph does. Storing the line on the
version is what puts it through the claim checker and under the approval, instead of being
sliced out of the body by a heuristic at render time — which would put the one piece of
copy nobody reviewed on the most visible surface of the post.
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("content_versions", sa.Column("card_line", sa.String(length=200),
                                                nullable=True))


def downgrade() -> None:
    op.drop_column("content_versions", "card_line")
