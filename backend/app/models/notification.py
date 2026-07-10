import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin


class NotificationCategory(str, enum.Enum):
    REMEDIATION = "remediation"
    TELEMETRY = "telemetry"
    ASSET = "asset"
    SYSTEM = "system"


class NotificationSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


def _enum_col(enum_cls, default):
    return mapped_column(
        Enum(
            enum_cls,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=default,
    )


class Notification(TimestampMixin, Base):
    """An org-wide alert feed item shown in the portal notification center. Read state is
    shared across the org (like a triage inbox) rather than per-user — the platform has
    one team acting on approvals and failures, not individual per-user mailboxes."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)

    category: Mapped[NotificationCategory] = _enum_col(NotificationCategory, NotificationCategory.SYSTEM)
    severity: Mapped[NotificationSeverity] = _enum_col(NotificationSeverity, NotificationSeverity.INFO)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    # Optional deep link rendered as a clickable action in the portal.
    link: Mapped[str | None] = mapped_column(String(300), nullable=True)

    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
