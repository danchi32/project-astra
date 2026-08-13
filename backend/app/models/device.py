import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin


class Device(TimestampMixin, Base):
    __tablename__ = "devices"
    __table_args__ = (UniqueConstraint("org_id", "machine_id", name="uq_devices_org_machine"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    # Stable hardware identifier (Windows MachineGuid) — dedupes re-enrollments.
    machine_id: Mapped[str] = mapped_column(String(100), nullable=False)
    os_version: Mapped[str] = mapped_column(String(100), nullable=False)
    serial_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    agent_version: Mapped[str] = mapped_column(String(20), nullable=False)
    logged_in_user: Mapped[str | None] = mapped_column(String(100), nullable=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Whether USB mass storage is blocked on the device, as the agent reads it from the
    # registry on each heartbeat — the actual state, not what ASTRA last asked for, so a port
    # reopened by hand or by Group Policy shows here as allowed. NULL means no agent new
    # enough to report it has checked in yet; the compliance count shows those as "unknown"
    # rather than guessing.
    usb_storage_blocked: Mapped[bool | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    # Hardware asset attributes — refreshed from the agent's inventory push.
    manufacturer: Mapped[str | None] = mapped_column(String(150), nullable=True)
    model: Mapped[str | None] = mapped_column(String(150), nullable=True)
    cpu_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    total_ram_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_storage_gb: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Fingerprints of the last inventory the agent sent, one per collection.
    #
    # The agent re-sends its FULL inventory every hour and the old code answered with
    # delete-all-then-insert-all. A device carries ~300 service rows, so that was ~600 row
    # writes per device per hour whether or not anything had changed — at 10k devices,
    # millions of dead tuples an hour for autovacuum to chase, which is what actually caps
    # the fleet size (compute scales with a config change; write churn doesn't).
    #
    # Comparing a hash of the incoming set against these lets an unchanged collection skip
    # the rewrite entirely. They live on `devices` rather than a side table because the
    # device row is already loaded during ingest, so checking costs no extra query.
    apps_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    services_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updates_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    events_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
