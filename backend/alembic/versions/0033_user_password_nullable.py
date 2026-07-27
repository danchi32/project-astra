"""Allow login-less (directory-only) users: make users.hashed_password nullable

An admin can create a user without a password; such a user exists for asset assignment,
offboarding and emails but cannot sign in to the portal.

Revision ID: 0033
Revises: 0032
Create Date: 2026-07-24
"""
import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "hashed_password", existing_type=sa.String(length=128), nullable=True)


def downgrade() -> None:
    op.alter_column("users", "hashed_password", existing_type=sa.String(length=128), nullable=False)
