"""Which relay device group an organisation's machines enroll into.

Additive: one nullable column on `organizations`. Nothing reads it until an operator
sets it, and a NULL means this org cannot provision remote support — which is the right
default for every org that exists today.

Two conditions must BOTH hold before a device is told to install the remote-support
agent: the org's plan must include remote control, and this column must be set. That is
deliberate belt-and-braces. The entitlement is a commercial decision and can be granted
by anyone who can edit an org; this is an operational one and requires somebody to have
actually created a group on the relay for that customer. Either alone is not enough,
because the failure modes differ — a mis-granted entitlement would otherwise push a
remote-access agent onto a fleet, and a missing group would otherwise enroll one
customer's machines into another's.

Revision ID: 0058
Revises: 0057
"""
import sqlalchemy as sa
from alembic import op

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("meshcentral_mesh_id", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("organizations", "meshcentral_mesh_id")
