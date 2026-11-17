import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin


class Deployment(TimestampMixin, Base):
    """One push of one action to many devices (A4) — "install Chrome on Finance, except X".

    The targets are resolved when it is created and each becomes an ordinary remediation task
    carrying this id, so tiers, approvals, the fleet circuit breaker and the audit trail all
    apply per device exactly as they do for a single fix. This row is only the envelope that
    lets the portal show the push as one thing with a per-device status.
    """

    __tablename__ = "deployments"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)
    action_id: Mapped[str] = mapped_column(String(50), nullable=False)
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # What was asked for (device / group / exclusion ids), kept for the record — the tasks
    # are what actually ran.
    targets: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # C2 canary rollout. `waves` is the plan made at creation: device ids per wave, the first
    # a single device, then 10%, then the rest. NULL means an all-at-once push (the A4 shape).
    # A wave's tasks are created only when it is released, so a device in a later wave has
    # nothing queued until the gate opens.
    waves: Mapped[list | None] = mapped_column(JSON, nullable=True)
    current_wave: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wave_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    halted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    halt_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
