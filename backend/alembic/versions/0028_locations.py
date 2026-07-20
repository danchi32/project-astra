"""Managed locations (seeded from existing asset locations)

Revision ID: 0028
Revises: 0027
Create Date: 2026-07-19
"""
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("org_id", "name", name="uq_locations_org_name"),
    )
    op.create_index("ix_locations_org_id", "locations", ["org_id"])

    # Seed the managed list from locations already typed on assets, so nothing is lost.
    # (Skipped in offline --sql mode, where there's no live connection to read from.)
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT DISTINCT org_id, TRIM(location) AS name FROM assets "
        "WHERE location IS NOT NULL AND LENGTH(TRIM(location)) > 0"
    ))
    existing = result.fetchall() if result is not None else []
    for org_id, name in existing:
        conn.execute(
            sa.text("INSERT INTO locations (id, org_id, name) VALUES (:id, :org_id, :name)"),
            {"id": str(uuid.uuid4()), "org_id": str(org_id), "name": name},
        )


def downgrade() -> None:
    op.drop_index("ix_locations_org_id", table_name="locations")
    op.drop_table("locations")
