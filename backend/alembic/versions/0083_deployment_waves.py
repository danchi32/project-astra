"""Canary rollout (C2): waves, the gate's position, and a halt on deployments.

Revision ID: 0083
Revises: 0082
"""
import sqlalchemy as sa

from alembic import op

revision = "0083"
down_revision = "0082"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("deployments", sa.Column("waves", sa.JSON(), nullable=True))
    op.add_column("deployments", sa.Column("current_wave", sa.Integer(), nullable=True))
    op.add_column("deployments", sa.Column("wave_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("deployments", sa.Column("halted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("deployments", sa.Column("halt_reason", sa.String(300), nullable=True))


def downgrade() -> None:
    for col in ("halt_reason", "halted_at", "wave_started_at", "current_wave", "waves"):
        op.drop_column("deployments", col)
