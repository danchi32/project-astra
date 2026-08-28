"""Logon sessions, device groups and user teams.

Three additions that arrive together because the Sessions view needs all of them: a table
of who is signed in where, a way to slice the fleet that is not "all 2,000 of them", and
the people side of the same idea.

`device_sessions` replaces nothing — `devices.logged_in_user` stays, because it is what the
device list column and every existing report read, and it is correct for the single-user
laptop that is most of a fleet. What it cannot do is describe a machine with more than one
person on it, which is exactly the case a technician goes looking for.

`devices.sessions_hash` is the same trick as apps_hash/services_hash: sessions ride on the
60-second telemetry push, so without a fingerprint this table would be rewritten every
minute for every device whether or not anyone had signed in or out.

Revision ID: 0055
Revises: 0054
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("sessions_hash", sa.String(length=64), nullable=True))

    op.create_table(
        "device_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=150), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("connection", sa.String(length=20), nullable=False),
        sa.Column("station", sa.String(length=60), nullable=True),
        sa.Column("client_name", sa.String(length=120), nullable=True),
        sa.Column("logon_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idle_seconds", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", "session_id",
                            name="uq_device_sessions_device_session"),
    )
    op.create_index("ix_device_sessions_device_id", "device_sessions", ["device_id"])
    op.create_index("ix_device_sessions_org_id", "device_sessions", ["org_id"])
    # The Sessions page's default view is "this org, active first". Both filters are on
    # every query it makes, so they are indexed together rather than separately.
    op.create_index("ix_device_sessions_org_state", "device_sessions", ["org_id", "state"])

    op.create_table(
        "device_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("colour", sa.String(length=9), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "name", name="uq_device_groups_org_name"),
    )
    op.create_index("ix_device_groups_org_id", "device_groups", ["org_id"])

    op.create_table(
        "device_group_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["device_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "device_id", name="uq_device_group_members"),
    )
    op.create_index("ix_device_group_members_group_id", "device_group_members", ["group_id"])
    op.create_index("ix_device_group_members_device_id", "device_group_members", ["device_id"])

    op.create_table(
        "user_teams",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("colour", sa.String(length=9), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "name", name="uq_user_teams_org_name"),
    )
    op.create_index("ix_user_teams_org_id", "user_teams", ["org_id"])

    op.create_table(
        "user_team_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["user_teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "user_id", name="uq_user_team_members"),
    )
    op.create_index("ix_user_team_members_team_id", "user_team_members", ["team_id"])
    op.create_index("ix_user_team_members_user_id", "user_team_members", ["user_id"])


def downgrade() -> None:
    for name in ("ix_user_team_members_user_id", "ix_user_team_members_team_id"):
        op.drop_index(name, table_name="user_team_members")
    op.drop_table("user_team_members")
    op.drop_index("ix_user_teams_org_id", table_name="user_teams")
    op.drop_table("user_teams")

    for name in ("ix_device_group_members_device_id", "ix_device_group_members_group_id"):
        op.drop_index(name, table_name="device_group_members")
    op.drop_table("device_group_members")
    op.drop_index("ix_device_groups_org_id", table_name="device_groups")
    op.drop_table("device_groups")

    for name in ("ix_device_sessions_org_state", "ix_device_sessions_org_id",
                 "ix_device_sessions_device_id"):
        op.drop_index(name, table_name="device_sessions")
    op.drop_table("device_sessions")

    op.drop_column("devices", "sessions_hash")
