"""Installed apps — per-user installs.

Adds scope ("machine" | "user") and user_name to device_installed_apps. Agents from 0.14 read
each signed-in person's own Uninstall key as well as the machine-wide ones, because the apps
that matter most for shadow-IT questions (ChatGPT, Claude, Cursor, Zoom, Ollama) install per
user by default and were invisible. Existing rows are all machine-wide, which the server
default says.

Revision ID: 0072
Revises: 0071
"""
import sqlalchemy as sa

from alembic import op

revision = "0072"
down_revision = "0071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("device_installed_apps") as batch:
        batch.add_column(
            sa.Column("scope", sa.String(length=10), nullable=False, server_default="machine")
        )
        batch.add_column(sa.Column("user_name", sa.String(length=256), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("device_installed_apps") as batch:
        batch.drop_column("user_name")
        batch.drop_column("scope")
