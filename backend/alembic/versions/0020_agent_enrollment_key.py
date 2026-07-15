"""Permanent per-org agent enrollment key

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-15
"""
import secrets

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("agent_enrollment_key", sa.String(length=80), nullable=True))
    # Backfill a unique permanent key for every existing organization.
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id FROM organizations WHERE agent_enrollment_key IS NULL")).fetchall()
    for (org_id,) in rows:
        conn.execute(
            sa.text("UPDATE organizations SET agent_enrollment_key = :k WHERE id = :i"),
            {"k": secrets.token_urlsafe(48), "i": org_id},
        )
    op.create_index(
        "ix_organizations_agent_enrollment_key", "organizations", ["agent_enrollment_key"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_organizations_agent_enrollment_key", table_name="organizations")
    op.drop_column("organizations", "agent_enrollment_key")
