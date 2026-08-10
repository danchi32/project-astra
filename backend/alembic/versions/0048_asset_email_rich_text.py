"""email_settings: rich-text asset email bodies

The template editor grew a formatting toolbar, so a body can now be HTML rather than plain
text. Two changes follow from that.

`asset_email_body_format` records which one a row holds. Every existing row is plain text
and has to keep rendering as plain text — escaped, with newlines turned into breaks — so it
defaults to "text" and only a save from the new editor sets "html". The alternative was
sniffing the content for tags, which reads a plain-text body that happens to contain "<3"
as markup and silently eats the rest of the sentence.

The body column also grows: 4000 characters was generous for plain text and tight for the
same message wrapped in markup, where a couple of formatted lists can cost more than the
words do.

Revision ID: 0048
Revises: 0047
"""
import sqlalchemy as sa
from alembic import op

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_settings",
        sa.Column(
            "asset_email_body_format",
            sa.String(length=10),
            nullable=False,
            server_default="text",
        ),
    )
    op.alter_column(
        "email_settings",
        "asset_email_body",
        existing_type=sa.String(length=4000),
        type_=sa.String(length=20000),
        existing_nullable=True,
    )


def downgrade() -> None:
    # Truncate rather than fail: a body written in the rich-text editor can exceed the old
    # limit, and a downgrade that errors out mid-rollback is worse than a shortened template
    # an admin can see and fix.
    op.execute(
        "UPDATE email_settings SET asset_email_body = LEFT(asset_email_body, 4000) "
        "WHERE LENGTH(asset_email_body) > 4000"
    )
    op.alter_column(
        "email_settings",
        "asset_email_body",
        existing_type=sa.String(length=20000),
        type_=sa.String(length=4000),
        existing_nullable=True,
    )
    op.drop_column("email_settings", "asset_email_body_format")
