import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ── Agent → Backend (ingestion) ────────────────────────────────────────────

class DiskInfo(BaseModel):
    drive: str
    total_gb: float
    used_gb: float
    free_gb: float


class EventLogEntry(BaseModel):
    log_name: str
    source: str
    event_id: int
    level: str
    message: str = Field(max_length=2000)
    occurred_at: datetime


class InstalledAppEntry(BaseModel):
    name: str = Field(max_length=300)
    version: str | None = Field(default=None, max_length=100)
    publisher: str | None = Field(default=None, max_length=200)
    install_date: str | None = Field(default=None, max_length=20)


class ServiceEntry(BaseModel):
    name: str = Field(max_length=200)
    display_name: str = Field(max_length=300)
    status: str = Field(max_length=30)
    start_type: str = Field(max_length=30)


class WindowsUpdateEntry(BaseModel):
    kb_article_id: str = Field(max_length=30)
    title: str = Field(max_length=400)
    is_installed: bool
    installed_on: str | None = Field(default=None, max_length=30)


class TelemetryPush(BaseModel):
    """Single payload the agent sends each cycle."""

    collected_at: datetime

    # Metrics — always present
    cpu_percent: float = Field(ge=0, le=100)
    ram_total_mb: int = Field(gt=0)
    ram_used_mb: int = Field(ge=0)
    disks: list[DiskInfo]

    # Inventory — sent periodically (agent may omit if unchanged)
    event_logs: list[EventLogEntry] = []
    installed_apps: list[InstalledAppEntry] = []
    services: list[ServiceEntry] = []
    windows_updates: list[WindowsUpdateEntry] = []


class TelemetryPushResponse(BaseModel):
    status: str = "accepted"


# ── Backend → Portal (read) ────────────────────────────────────────────────

class TelemetrySnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    device_id: uuid.UUID
    cpu_percent: float
    ram_total_mb: int
    ram_used_mb: int
    disks: list[dict[str, Any]]
    collected_at: datetime
    created_at: datetime


class DeviceEventLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    device_id: uuid.UUID
    log_name: str
    source: str
    event_id: int
    level: str
    message: str
    occurred_at: datetime


class DeviceInstalledAppRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    device_id: uuid.UUID
    name: str
    version: str | None
    publisher: str | None
    install_date: str | None
    collected_at: datetime


class DeviceServiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    device_id: uuid.UUID
    name: str
    display_name: str
    status: str
    start_type: str
    collected_at: datetime


class DeviceWindowsUpdateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    device_id: uuid.UUID
    kb_article_id: str
    title: str
    is_installed: bool
    installed_on: str | None
    collected_at: datetime


# ── Dashboard summary ──────────────────────────────────────────────────────

class DashboardSummary(BaseModel):
    total_devices: int
    online_devices: int
    offline_devices: int
    avg_cpu_percent: float
    avg_ram_percent: float
    critical_event_count: int
    pending_update_count: int
