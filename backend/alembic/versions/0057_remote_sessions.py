"""Remote control: the record of who asked, who answered, and for how long.

Purely additive. One new table and one nullable column on `devices`, so every existing
read and write behaves exactly as it did before this migration. Nothing consults either
yet — the API that does is gated behind an entitlement no plan grants.

Two columns are worth explaining here rather than only in the model:

`status` separates `declined` from `no_response`. They are not the same event and they
need different follow-ups — a refusal ends the matter, silence means try again or phone
the person. MeshCentral collapses both into "local user rejected", which told a technician
during the spike that their customer had refused a session the customer never saw. ASTRA
records what actually happened.

`devices.meshcentral_node_id` is a mapping column and nothing more. ASTRA's own
`machine_id` stays the identity of a device; the remote-control node id hangs beneath it.
During the spike two disposable VMs reported the same machine GUID and appeared as two
identical rows, one of them dead — a re-imaged laptop does the same thing on a customer's
fleet, and the row nobody can tell apart is the row they click.

Revision ID: 0057
Revises: 0056
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column("meshcentral_node_id", sa.String(length=128), nullable=True),
    )

    op.create_table(
        "remote_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Who asked. Never null: a session nobody is accountable for must not exist.
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Shown to the person being asked, and the half of the audit trail worth reading.
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        # The provider's own handle for the session, once one exists.
        sa.Column("provider_session_id", sa.String(length=128), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        # Designed in now so adding recording later is a feature, not a migration on a
        # table that by then has live rows in it.
        sa.Column("recording_uri", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_remote_sessions_org_id", "remote_sessions", ["org_id"])
    op.create_index("ix_remote_sessions_device_id", "remote_sessions", ["device_id"])
    op.create_index("ix_remote_sessions_status", "remote_sessions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_remote_sessions_status", table_name="remote_sessions")
    op.drop_index("ix_remote_sessions_device_id", table_name="remote_sessions")
    op.drop_index("ix_remote_sessions_org_id", table_name="remote_sessions")
    op.drop_table("remote_sessions")
    op.drop_column("devices", "meshcentral_node_id")
