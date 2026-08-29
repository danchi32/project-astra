"""leads and lead_submissions

Revision ID: 0001
Revises:
Create Date: 2026-08-28

The first migration of the marketing database. Note that this is a *different* database
from the product's — nothing here references organizations, users or devices, and it must
stay that way. A foreign key from a lead to a customer record is the seam through which
marketing data and customer data would eventually merge.
"""
import sqlalchemy as sa
from alembic import op

from app.models.base import GUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=True),
        sa.Column("company", sa.String(length=200), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("email_domain", sa.String(length=255), nullable=True),
        sa.Column("is_free_email", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="new"),
        sa.Column("tier", sa.String(length=12), nullable=False, server_default="unscored"),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score_reason", sa.Text(), nullable=True),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_source", sa.String(length=120), nullable=True),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_contacted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("crm_provider", sa.String(length=30), nullable=True),
        sa.Column("crm_record_id", sa.String(length=64), nullable=True),
        sa.Column("crm_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    # Unique, not merely indexed: this constraint *is* the deduplication rule. Two
    # concurrent first-time submissions from the same address race here on purpose, and
    # LeadService.capture catches the loser and attaches its submission to the winner.
    op.create_index("ix_leads_email", "leads", ["email"], unique=True)
    op.create_index("ix_leads_email_domain", "leads", ["email_domain"])
    op.create_index("ix_leads_status", "leads", ["status"])
    op.create_index("ix_leads_tier", "leads", ["tier"])
    op.create_index("ix_leads_crm_record_id", "leads", ["crm_record_id"])

    op.create_table(
        "lead_submissions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("interest", sa.String(length=80), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("landing_page", sa.String(length=1000), nullable=True),
        sa.Column("referrer", sa.String(length=1000), nullable=True),
        sa.Column("utm_source", sa.String(length=160), nullable=True),
        sa.Column("utm_medium", sa.String(length=160), nullable=True),
        sa.Column("utm_campaign", sa.String(length=160), nullable=True),
        sa.Column("utm_content", sa.String(length=160), nullable=True),
        sa.Column("utm_term", sa.String(length=160), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispatch_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_lead_submissions_lead_id", "lead_submissions", ["lead_id"])
    op.create_index("ix_lead_submissions_source", "lead_submissions", ["source"])
    op.create_index("ix_lead_submissions_utm_source", "lead_submissions", ["utm_source"])
    op.create_index("ix_lead_submissions_utm_campaign", "lead_submissions", ["utm_campaign"])
    # The replay sweeper's query: undispatched, oldest first. Partial on Postgres so the
    # index stays tiny — it only ever holds the backlog, which is normally empty.
    op.create_index(
        "ix_lead_submissions_undispatched",
        "lead_submissions",
        ["created_at"],
        postgresql_where=sa.text("dispatched_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("lead_submissions")
    op.drop_table("leads")
