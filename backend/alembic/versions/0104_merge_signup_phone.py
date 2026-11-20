"""Join the two migration heads: main's 0086a (signup phone) and phase 3's 0087..0103.

Both started from 0086, so after phase 3 merges into main there are two heads and
`alembic upgrade head` would refuse. This revision changes nothing; it only joins them.
Production (at 0086a) runs 0087..0103 and then this; a database at 0103 runs 0086a and then this.

Revision ID: 0104
Revises: 0103, 0086a
"""

revision = "0104"
down_revision = ("0103", "0086a")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
