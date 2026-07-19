import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin, utcnow


class AssetCategory(str, enum.Enum):
    LAPTOP = "laptop"
    DESKTOP = "desktop"
    SERVER = "server"
    MONITOR = "monitor"
    PHONE = "phone"
    TABLET = "tablet"
    PERIPHERAL = "peripheral"
    NETWORK = "network"
    LICENSE = "license"
    SOFTWARE = "software"
    OTHER = "other"


class AssetStatus(str, enum.Enum):
    IN_USE = "in_use"
    IN_STORAGE = "in_storage"
    IN_REPAIR = "in_repair"
    RETIRED = "retired"
    LOST = "lost"


class AcknowledgementStatus(str, enum.Enum):
    NOT_REQUIRED = "not_required"  # never assigned, or assignment cleared
    PENDING = "pending"            # assigned; acknowledgement email sent, awaiting receipt
    ACKNOWLEDGED = "acknowledged"  # the assignee confirmed receipt


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


class Asset(TimestampMixin, Base):
    """An item in the org's IT asset register. May be linked to an auto-discovered
    device (device_id) or tracked standalone (monitors, phones, licenses, peripherals)."""

    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)

    asset_tag: Mapped[str | None] = mapped_column(String(60), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[AssetCategory] = _enum_col(AssetCategory, AssetCategory.OTHER)
    status: Mapped[AssetStatus] = _enum_col(AssetStatus, AssetStatus.IN_USE)

    # Optional links: who holds it, and the auto-discovered device it corresponds to.
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("devices.id", ondelete="SET NULL"), nullable=True
    )

    manufacturer: Mapped[str | None] = mapped_column(String(150), nullable=True)
    model: Mapped[str | None] = mapped_column(String(150), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(150), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # ISO date strings (YYYY-MM-DD) keep this dialect-simple; cost is a plain number.
    purchase_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    warranty_expiry: Mapped[str | None] = mapped_column(String(10), nullable=True)
    purchase_cost: Mapped[float | None] = mapped_column(Float, nullable=True)

    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    # Assignment acknowledgement: when an asset is assigned to a user we email them a
    # receipt-confirmation link; clicking it flips this to acknowledged.
    acknowledgement_status: Mapped[AcknowledgementStatus] = _enum_col(
        AcknowledgementStatus, AcknowledgementStatus.NOT_REQUIRED
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ack_token: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
