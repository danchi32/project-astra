"""The relay user a viewer link for an organisation's devices logs in as.

Additive: one nullable column on `organizations`, the companion to
`meshcentral_mesh_id` from 0058. The mesh id says which device group an org's machines
enroll into; this says which relay account a viewer cookie names when a technician opens
one of those machines.

They are separate columns because they are separate halves of the isolation boundary and
have different failure modes. The mesh id keeps one org's machines out of another's group.
This keeps one org's technician out of another's group: the account named here is scoped
on the relay to this org's group alone and is not a site admin, so a viewer URL whose node
id has been edited to point elsewhere is refused rather than honoured. NULL means no viewer
link is issued — there is deliberately no fallback to a shared admin account, because a
shared admin is the exact cross-tenant leak this exists to close.

Revision ID: 0059
Revises: 0058
"""
import sqlalchemy as sa
from alembic import op

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("meshcentral_user_id", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("organizations", "meshcentral_user_id")
