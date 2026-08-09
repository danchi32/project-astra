"""email_settings: make the sending identity a choice, and give replies somewhere to go

Two things were true and neither was visible.

Mail already went out one of two ways — as the org from their verified domain, or from
ASTRA's address with "(via ASTRA)" in the display name. But the second was a *fallback*,
reached only by not having finished DNS setup, so the portal presented it as an unfinished
state. Publishing DNS records is a request to another team in most companies; an org that
would rather not is not half-configured, it has made a choice. `method` now records it.

And nothing carried a Reply-To. An employee who replied to an asset email sent from our
address wrote to astra@technomateai.com, where nobody reads a customer's staff mail. Their
question went nowhere, silently, which is worse than the mail not being sent at all.

Existing rows: UNCONFIGURED means they never set a sending address, so the shared sender is
what they have been using all along — recorded as such. PENDING, VERIFIED and FAILED are
left on `dns`, because each one represents an intent to use their own domain that this
migration has no business overruling.

Revision ID: 0046
Revises: 0045
"""
import sqlalchemy as sa
from alembic import op

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("email_settings", sa.Column("reply_to", sa.String(320), nullable=True))
    op.execute(
        """
        UPDATE email_settings
           SET method = 'shared'
         WHERE status = 'unconfigured'
        """
    )


def downgrade() -> None:
    # 'shared' does not exist in the old enum, so anything on it has to go somewhere.
    # 'dns' is where those rows were before this migration ran.
    op.execute("UPDATE email_settings SET method = 'dns' WHERE method = 'shared'")
    op.drop_column("email_settings", "reply_to")
