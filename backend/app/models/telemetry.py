import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin


class TelemetrySnapshot(TimestampMixin, Base):
    """One snapshot per telemetry push from the agent (≈ every 60 s)."""

    __tablename__ = "telemetry_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)

    cpu_percent: Mapped[float] = mapped_column(Float, nullable=False)
    ram_total_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    ram_used_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    # JSON list: [{drive, total_gb, used_gb, free_gb}]
    disks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)

    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TelemetryDailyRollup(TimestampMixin, Base):
    """One aggregated row per device per day, written as snapshots arrive.

    Raw snapshots are pruned after a short retention window (they are only ever read as
    "the latest" or "the last 60"), which would otherwise destroy all history. This table
    keeps that history permanently at ~1 row/device/day — cheap enough to retain forever
    and enough to build long-range trend charts from later.
    """

    __tablename__ = "telemetry_daily_rollups"
    __table_args__ = (
        UniqueConstraint("device_id", "day", name="uq_telemetry_rollup_device_day"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)

    # UTC calendar day this row aggregates.
    day: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    samples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    cpu_avg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cpu_max: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ram_used_avg_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ram_used_max_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Worst free-space percentage seen across the device's disks that day.
    disk_free_min_pct: Mapped[float | None] = mapped_column(Float, nullable=True)


class DeviceEventLog(TimestampMixin, Base):
    """Recent Windows Event Viewer entries (errors / warnings) from the agent."""

    __tablename__ = "device_event_logs"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)

    log_name: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    event_id: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False)   # Error, Warning, Information
    message: Mapped[str] = mapped_column(String(2000), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DeviceInstalledApp(TimestampMixin, Base):
    """Installed applications as read from the Windows registry."""

    __tablename__ = "device_installed_apps"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(200), nullable=True)
    install_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DeviceService(TimestampMixin, Base):
    """Windows services snapshot."""

    __tablename__ = "device_services"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)    # Running, Stopped, …
    start_type: Mapped[str] = mapped_column(String(30), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DeviceWindowsUpdate(TimestampMixin, Base):
    """Pending / recently installed Windows updates."""

    __tablename__ = "device_windows_updates"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)

    kb_article_id: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(400), nullable=False)
    is_installed: Mapped[bool] = mapped_column(nullable=False)
    installed_on: Mapped[str | None] = mapped_column(String(30), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
