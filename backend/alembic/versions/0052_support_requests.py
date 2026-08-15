"""Let an organization raise a problem with ASTRA itself, and get an answer back.

Two tables. `support_requests` is the thread; `support_request_messages` is the
conversation on it, from either side — without the second table the feature is a suggestion
box, and a customer who cannot see a reply assumes nobody read it.

`diagnostics` is a JSON snapshot taken when the request is submitted, not a live lookup.
A support thread has to keep explaining itself a week later, when the fleet it describes
has already moved on.

Revision ID: 0052
Revises: 0051
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "support_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reference", sa.String(length=20), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("priority", sa.String(length=10), nullable=False),
        sa.Column("diagnostics", sa.JSON(), nullable=True),
        sa.Column("last_reply_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        # The thread outlives the person who opened it.
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_support_requests_org_id", "support_requests", ["org_id"])
    op.create_index(
        "ix_support_requests_created_by_user_id", "support_requests", ["created_by_user_id"]
    )
    op.create_index(
        "ix_support_requests_reference", "support_requests", ["reference"], unique=True
    )
    op.create_index("ix_support_requests_status", "support_requests", ["status"])
    op.create_index("ix_support_requests_priority", "support_requests", ["priority"])
    op.create_index("ix_support_requests_category", "support_requests", ["category"])
    op.create_index("ix_support_requests_last_reply_at", "support_requests", ["last_reply_at"])

    op.create_table(
        "support_request_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("from_operator", sa.Boolean(), nullable=False),
        sa.Column("body", sa.String(length=10000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["request_id"], ["support_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_support_request_messages_request_id", "support_request_messages", ["request_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_support_request_messages_request_id", table_name="support_request_messages"
    )
    op.drop_table("support_request_messages")
    for name in (
        "ix_support_requests_last_reply_at",
        "ix_support_requests_category",
        "ix_support_requests_priority",
        "ix_support_requests_status",
        "ix_support_requests_reference",
        "ix_support_requests_created_by_user_id",
        "ix_support_requests_org_id",
    ):
        op.drop_index(name, table_name="support_requests")
    op.drop_table("support_requests")
