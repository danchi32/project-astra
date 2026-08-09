"""email_settings.asset_email_cc: copy IT on the asset acknowledgement

An admin assigns a laptop, the employee gets an email, and until now that was the last
anybody heard of it unless they went looking in the portal. The org wants a copy in their
own mailbox, and — more usefully — wants the employee's Reply All to reach them.

CC and not BCC, which is the whole point: a BCC'd address is invisible to the recipient's
mail client, so Reply All would go to the sender alone and IT would still miss the answer.

Scoped to this one message. Password resets, OTPs and login alerts are written for one
person, and copying an administrator on them would hand that person's account to somebody
else.

Revision ID: 0047
Revises: 0046
"""
import sqlalchemy as sa
from alembic import op

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("email_settings", sa.Column("asset_email_cc", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("email_settings", "asset_email_cc")
