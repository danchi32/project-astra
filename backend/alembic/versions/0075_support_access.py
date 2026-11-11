"""Customer-granted SAVIO support access.

Adds organizations.support_access_until. A platform admin's read-only "view as" token is
refused — when minted and on every request — unless the customer's admin has opened a window
from Settings (1/24/72 h). NULL for every existing org, i.e. no access until granted.

Revision ID: 0075
Revises: 0074
"""
import sqlalchemy as sa

from alembic import op

revision = "0075"
down_revision = "0074"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("organizations") as batch:
        batch.add_column(sa.Column("support_access_until", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("organizations") as batch:
        batch.drop_column("support_access_until")
