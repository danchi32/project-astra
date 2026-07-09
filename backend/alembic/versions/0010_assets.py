"""Asset register

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-09
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

category_enum = sa.Enum(
    "laptop", "desktop", "server", "monitor", "phone", "tablet", "peripheral",
    "network", "license", "software", "other",
    name="assetcategory", native_enum=False, length=20,
)
status_enum = sa.Enum(
    "in_use", "in_storage", "in_repair", "retired", "lost",
    name="assetstatus", native_enum=False, length=20,
)


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_tag", sa.String(60), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", category_enum, nullable=False),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("assigned_to_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("manufacturer", sa.String(150), nullable=True),
        sa.Column("model", sa.String(150), nullable=True),
        sa.Column("serial_number", sa.String(150), nullable=True),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("purchase_date", sa.String(10), nullable=True),
        sa.Column("warranty_expiry", sa.String(10), nullable=True),
        sa.Column("purchase_cost", sa.Float(), nullable=True),
        sa.Column("notes", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_assets_org_id", "assets", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_assets_org_id", table_name="assets")
    op.drop_table("assets")
