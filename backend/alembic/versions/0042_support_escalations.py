"""Escalations: problems ASTRA could not fix, handed to a human

One additive table. It carries the consent record, the deduplication key and the pointer to
the ticket in the customer's own helpdesk — three jobs that all need the same row, and none
of which can be reconstructed after the fact.

Revision ID: 0042
Revises: 0041
Create Date: 2026-08-07
"""
import sqlalchemy as sa
from alembic import op

from app.models.base import GUID

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "support_escalations",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("org_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("conversation_id", GUID(), nullable=True, index=True),
        sa.Column("device_id", GUID(), nullable=True, index=True),
        sa.Column("user_id", GUID(), nullable=True, index=True),
        sa.Column("problem_summary", sa.String(length=1000), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("embedding_model", sa.String(length=60), nullable=True),
        sa.Column("action_id", sa.String(length=50), nullable=True),
        sa.Column("dossier", sa.String(length=20000), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=False, server_default="offered",
                  index=True),
        sa.Column("provider", sa.String(length=30), nullable=True),
        sa.Column("external_ticket_id", sa.String(length=60), nullable=True, index=True),
        sa.Column("external_url", sa.String(length=500), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("raised_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    # The dedupe lookup runs before every offer and every raise: "an open ticket for this
    # device, recently". That is the query worth an index, not the individual columns.
    op.create_index(
        "ix_support_escalations_dedupe",
        "support_escalations",
        ["org_id", "device_id", "state", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_support_escalations_dedupe", table_name="support_escalations")
    op.drop_table("support_escalations")
