"""webhook_events: make a billing webhook applyable exactly once

A verified signature proved a payload was authentic, never that it was new. Every rail here
signs the body, so a captured `subscription.activated` payload stayed valid forever —
replaying it after a cancellation put the org back to ACTIVE, which is the flag that decides
whether they can still make changes. Delivery order is not guaranteed either, so a delayed
`activated` landing after `canceled` did the same thing with no attacker involved.

This table is the record of what has already been applied. The unique constraint is the
guard — an `if exists` check in application code loses to two deliveries racing.

Revision ID: 0044
Revises: 0043
"""
import sqlalchemy as sa
from alembic import op

from app.models.base import GUID

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_events",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("event_id", sa.String(200), nullable=False),
        sa.Column(
            "org_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_status", sa.String(40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "event_id", name="uq_webhook_events_provider_event"),
    )
    op.create_index("ix_webhook_events_provider", "webhook_events", ["provider"])
    op.create_index("ix_webhook_events_org_id", "webhook_events", ["org_id"])
    # The staleness check reads the newest event for one org; without this it is a scan of
    # every webhook ever received, on the request path of every webhook.
    op.create_index(
        "ix_webhook_events_org_occurred", "webhook_events", ["org_id", "occurred_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_webhook_events_org_occurred", table_name="webhook_events")
    op.drop_index("ix_webhook_events_org_id", table_name="webhook_events")
    op.drop_index("ix_webhook_events_provider", table_name="webhook_events")
    op.drop_table("webhook_events")
