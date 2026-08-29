"""content items, versions and events

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-29

The tables behind the publish gate. Three, not one, and the split is the design:

  content_items    holds state, and — critically — `approved_version_id`
  content_versions holds the words, one row per draft, never updated
  content_events   holds what happened, append-only

Approval points at a version rather than living on the item, so approve → revise →
publish cannot put unreviewed words in front of anyone. A single table with a status
column permits exactly that sequence, and every step of it looks legitimate afterwards.
"""
import sqlalchemy as sa
from alembic import op

from app.models.base import GUID

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_items",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("campaign", sa.String(length=160), nullable=True),
        sa.Column("brief", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("current_version_id", GUID(), nullable=True),
        sa.Column("approved_version_id", GUID(), nullable=True),
        sa.Column("approved_by", sa.String(length=160), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_url", sa.String(length=1000), nullable=True),
        sa.Column("published_ref", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_content_items_channel", "content_items", ["channel"])
    op.create_index("ix_content_items_campaign", "content_items", ["campaign"])
    op.create_index("ix_content_items_status", "content_items", ["status"])
    # The scheduler's query: everything approved and due. Partial on Postgres so the index
    # holds only the queue rather than every item ever written.
    op.create_index(
        "ix_content_items_due",
        "content_items",
        ["scheduled_for"],
        postgresql_where=sa.text("status = 'scheduled'"),
    )

    op.create_table(
        "content_versions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("content_item_id", GUID(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("headline", sa.String(length=300), nullable=True),
        sa.Column("hashtags", sa.String(length=300), nullable=True),
        sa.Column("cta", sa.String(length=200), nullable=True),
        sa.Column("media_url", sa.String(length=1000), nullable=True),
        sa.Column("authored_by", sa.String(length=120), nullable=True),
        sa.Column("revision_reason", sa.Text(), nullable=True),
        sa.Column("check_result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"], ondelete="CASCADE"),
        # "Approve v2" has to mean one thing. Without this a race could write two v2s and
        # an approval would name a version number that matches two sets of words.
        sa.UniqueConstraint("content_item_id", "version_number", name="uq_version_per_item"),
    )
    op.create_index("ix_content_versions_item", "content_versions", ["content_item_id"])

    op.create_table(
        "content_events",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("content_item_id", GUID(), nullable=False),
        sa.Column("version_id", GUID(), nullable=True),
        sa.Column("event", sa.String(length=24), nullable=False),
        sa.Column("actor", sa.String(length=160), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_content_events_item", "content_events", ["content_item_id"])
    op.create_index("ix_content_events_event", "content_events", ["event"])


def downgrade() -> None:
    op.drop_table("content_events")
    op.drop_table("content_versions")
    op.drop_table("content_items")
