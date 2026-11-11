import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin


class AlertState(TimestampMixin, Base):
    """The last known state of one early-warning check on one device.

    It exists so alerts are edge-triggered: a notification fires when a check goes from
    healthy to alerting (and a quiet "recovered" on the way back), never once a minute for as
    long as the problem lasts. One row per (device, check), updated in place.
    """

    __tablename__ = "alert_states"
    __table_args__ = (UniqueConstraint("device_id", "check_key", name="uq_alert_states_device_check"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)
    check_key: Mapped[str] = mapped_column(String(40), nullable=False)
    state: Mapped[str] = mapped_column(String(10), nullable=False)  # "alerting" | "ok"
    since: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    detail: Mapped[str | None] = mapped_column(String(300), nullable=True)
