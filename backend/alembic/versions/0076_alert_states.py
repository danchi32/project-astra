"""Early-warning alerts (N1).

alert_states: last known state of each early-warning check per device, so alerts fire on a
change (healthy -> alerting, and back) rather than on every push. organization_settings
gains email_critical_alerts (default on): whether critical alerts are also emailed to the
org's admins.

Revision ID: 0076
Revises: 0075
"""
import sqlalchemy as sa

from alembic import op
from app.models.base import GUID

revision = "0076"
down_revision = "0075"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_states",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("device_id", GUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("org_id", GUID(), nullable=False),
        sa.Column("check_key", sa.String(length=40), nullable=False),
        sa.Column("state", sa.String(length=10), nullable=False),
        sa.Column("since", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detail", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("device_id", "check_key", name="uq_alert_states_device_check"),
    )
    op.create_index("ix_alert_states_device_id", "alert_states", ["device_id"])
    op.create_index("ix_alert_states_org_id", "alert_states", ["org_id"])
    with op.batch_alter_table("organization_settings") as batch:
        batch.add_column(sa.Column("email_critical_alerts", sa.Boolean(), nullable=False,
                                   server_default=sa.true()))


def downgrade() -> None:
    with op.batch_alter_table("organization_settings") as batch:
        batch.drop_column("email_critical_alerts")
    op.drop_index("ix_alert_states_org_id", table_name="alert_states")
    op.drop_index("ix_alert_states_device_id", table_name="alert_states")
    op.drop_table("alert_states")
