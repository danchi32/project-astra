"""Telemetry daily rollups (so raw snapshots can be pruned without losing history)

Adds telemetry_daily_rollups: one aggregated row per device per day. Purely additive —
telemetry_snapshots itself is untouched.

Revision ID: 0035
Revises: 0034
Create Date: 2026-07-30
"""
import sqlalchemy as sa
from alembic import op

from app.models.base import GUID

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telemetry_daily_rollups",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("device_id", GUID(), nullable=False),
        sa.Column("org_id", GUID(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("samples", sa.Integer(), nullable=False),
        sa.Column("cpu_avg", sa.Float(), nullable=False),
        sa.Column("cpu_max", sa.Float(), nullable=False),
        sa.Column("ram_used_avg_mb", sa.Integer(), nullable=False),
        sa.Column("ram_used_max_mb", sa.Integer(), nullable=False),
        sa.Column("disk_free_min_pct", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", "day", name="uq_telemetry_rollup_device_day"),
    )
    op.create_index(
        "ix_telemetry_daily_rollups_device_id", "telemetry_daily_rollups", ["device_id"]
    )
    op.create_index(
        "ix_telemetry_daily_rollups_org_id", "telemetry_daily_rollups", ["org_id"]
    )
    op.create_index("ix_telemetry_daily_rollups_day", "telemetry_daily_rollups", ["day"])

    # Pruning walks (device_id, collected_at); without this the delete does a seq scan
    # over a table that grows by 1 row/device/minute.
    op.create_index(
        "ix_telemetry_snapshots_device_collected",
        "telemetry_snapshots",
        ["device_id", "collected_at"],
    )

    # Backfill from the snapshots already in the table. Without this, the first ingest
    # after deploy prunes every snapshot older than the retention window while its rollup
    # row has never been written — silently destroying all history that predates this
    # migration. Rolling it up here means pruning only ever drops rows we've aggregated.
    #
    # disk_free_min_pct stays NULL for backfilled days: it lives inside the `disks` JSON
    # and extracting it portably in SQL isn't worth it — new ingests populate it.
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            INSERT INTO telemetry_daily_rollups (
                id, device_id, org_id, day, samples,
                cpu_avg, cpu_max, ram_used_avg_mb, ram_used_max_mb,
                disk_free_min_pct, created_at
            )
            SELECT gen_random_uuid(), device_id, org_id,
                   (collected_at AT TIME ZONE 'UTC')::date,
                   count(*), avg(cpu_percent), max(cpu_percent),
                   round(avg(ram_used_mb))::int, max(ram_used_mb),
                   NULL, now()
            FROM telemetry_snapshots
            GROUP BY device_id, org_id, (collected_at AT TIME ZONE 'UTC')::date
            ON CONFLICT (device_id, day) DO NOTHING
            """
        )


def downgrade() -> None:
    op.drop_index(
        "ix_telemetry_snapshots_device_collected", table_name="telemetry_snapshots"
    )
    op.drop_index("ix_telemetry_daily_rollups_day", table_name="telemetry_daily_rollups")
    op.drop_index("ix_telemetry_daily_rollups_org_id", table_name="telemetry_daily_rollups")
    op.drop_index(
        "ix_telemetry_daily_rollups_device_id", table_name="telemetry_daily_rollups"
    )
    op.drop_table("telemetry_daily_rollups")
