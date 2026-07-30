"""Inventory fingerprints on devices, so an unchanged collection skips the rewrite

The agent re-sends its full inventory hourly and ingest answered with
delete-all-then-insert-all per collection. With ~300 service rows per device that is ~600
row writes/device/hour regardless of whether anything changed — the dominant source of
write churn, and the real ceiling on fleet size.

Purely additive: four nullable columns. Existing rows start NULL, so the first push after
deploy is treated as changed and writes normally, which also seeds the fingerprints.

Revision ID: 0036
Revises: 0035
Create Date: 2026-07-30
"""
import sqlalchemy as sa
from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None

_COLUMNS = ("apps_hash", "services_hash", "updates_hash", "events_hash")


def upgrade() -> None:
    for name in _COLUMNS:
        op.add_column("devices", sa.Column(name, sa.String(length=64), nullable=True))


def downgrade() -> None:
    for name in _COLUMNS:
        op.drop_column("devices", name)
