"""Add hardware asset fields to devices

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("manufacturer", sa.String(150), nullable=True))
    op.add_column("devices", sa.Column("model", sa.String(150), nullable=True))
    op.add_column("devices", sa.Column("cpu_name", sa.String(200), nullable=True))
    op.add_column("devices", sa.Column("total_ram_mb", sa.Integer(), nullable=True))
    op.add_column("devices", sa.Column("total_storage_gb", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("devices", "total_storage_gb")
    op.drop_column("devices", "total_ram_mb")
    op.drop_column("devices", "cpu_name")
    op.drop_column("devices", "model")
    op.drop_column("devices", "manufacturer")
