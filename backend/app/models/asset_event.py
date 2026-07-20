import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin, utcnow


class AssetEventType(str, enum.Enum):
    """A lifecycle event on an asset — the entries that make up its "passport"."""
    CREATED = "created"                    # to_value = initial status
    ASSIGNED = "assigned"                  # from_value/to_value = holder names; user_id = new holder
    UNASSIGNED = "unassigned"              # from_value = prior holder name
    STATUS_CHANGED = "status_changed"      # from_value/to_value = status
    LOCATION_CHANGED = "location_changed"  # from_value/to_value = location name
    ACKNOWLEDGED = "acknowledged"          # to_value = holder who confirmed receipt
    NOTE = "note"                          # free-text note (note field)


class AssetEvent(TimestampMixin, Base):
    """One immutable entry in an asset's history. Values are stored as human-readable
    SNAPSHOTS (status label, location name, holder name at the time) so the passport stays
    accurate even if a user or location is later renamed or deleted."""

    __tablename__ = "asset_events"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    event_type: Mapped[AssetEventType] = mapped_column(
        Enum(AssetEventType, native_enum=False, length=24,
             values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)   # who did it
    user_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)    # assignee (assign events)
    from_value: Mapped[str | None] = mapped_column(String(200), nullable=True)
    to_value: Mapped[str | None] = mapped_column(String(200), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # When the event happened. Overridable when seeding historical "created" events.
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True
    )
