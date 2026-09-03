"""Configurable AI assistants: identity rows and versioned behaviour.

Purely additive. Two new tables, no column added to and no column changed on anything that
already exists, so nothing running reads or writes differently after this migration. The
cognitive engine does not consult these tables yet — that is a separate, tested change.

`assistants.published_version_id` carries no foreign key on purpose: assistant_versions
already points back at assistants, and a circular constraint would need `use_alter`
ceremony to buy integrity this codebase does not enforce on comparable columns
(`audit_logs.actor_id`, the billing provider ids) either.

Revision ID: 0056
Revises: 0055
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        # NULL = built-in, owned by the platform operator, visible to every org.
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("published_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assistants_org_id", "assistants", ["org_id"])

    op.create_table(
        "assistant_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assistant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        # Every behaviour column is nullable: NULL means "use the server default", which is
        # what lets a seeded row reproduce today's behaviour exactly.
        sa.Column("system_prompt", sa.String(length=20000), nullable=True),
        sa.Column("model", sa.String(length=60), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("max_tool_iterations", sa.Integer(), nullable=True),
        sa.Column("tool_ids", sa.JSON(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assistant_id"], ["assistants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assistant_id", "version_no", name="uq_assistant_versions_no"),
    )
    op.create_index("ix_assistant_versions_assistant_id", "assistant_versions", ["assistant_id"])
    op.create_index("ix_assistant_versions_status", "assistant_versions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_assistant_versions_status", table_name="assistant_versions")
    op.drop_index("ix_assistant_versions_assistant_id", table_name="assistant_versions")
    op.drop_table("assistant_versions")
    op.drop_index("ix_assistants_org_id", table_name="assistants")
    op.drop_table("assistants")
