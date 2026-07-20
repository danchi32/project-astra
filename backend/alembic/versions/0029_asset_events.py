"""Asset lifecycle event log (device passport)

Revision ID: 0029
Revises: 0028
Create Date: 2026-07-20
"""
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=24), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("from_value", sa.String(length=200), nullable=True),
        sa.Column("to_value", sa.String(length=200), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_asset_events_org_id", "asset_events", ["org_id"])
    op.create_index("ix_asset_events_asset_id", "asset_events", ["asset_id"])
    op.create_index("ix_asset_events_occurred_at", "asset_events", ["occurred_at"])

    # Seed a 'created' event for every existing asset so its passport isn't empty. The
    # initial status is the asset's current status (the best we can know retroactively).
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT id, org_id, status, created_at FROM assets"
    ))
    rows = result.fetchall() if result is not None else []
    for asset_id, org_id, status, created_at in rows:
        conn.execute(
            sa.text(
                "INSERT INTO asset_events "
                "(id, org_id, asset_id, event_type, to_value, occurred_at, created_at, updated_at) "
                "VALUES (:id, :org_id, :asset_id, 'created', :status, :ts, :ts, :ts)"
            ),
            {"id": str(uuid.uuid4()), "org_id": str(org_id), "asset_id": str(asset_id),
             "status": status, "ts": created_at},
        )


def downgrade() -> None:
    op.drop_index("ix_asset_events_occurred_at", table_name="asset_events")
    op.drop_index("ix_asset_events_asset_id", table_name="asset_events")
    op.drop_index("ix_asset_events_org_id", table_name="asset_events")
    op.drop_table("asset_events")
