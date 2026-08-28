import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.telemetry import UPDATE_INSTALLED, UPDATE_PENDING


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
    # Sent by agents that can tell the states apart. Optional: agents released before this
    # send only is_installed, and `state` below folds that into the two states it can mean
    # rather than rejecting the push or inventing detail the agent never reported.
    state: Literal["pending", "pending_restart", "failed", "installed"] | None = None
    error_code: str | None = Field(default=None, max_length=20)

    @property
    def resolved_state(self) -> str:
        if self.state is not None:
            return self.state
        return UPDATE_INSTALLED if self.is_installed else UPDATE_PENDING


class SessionEntry(BaseModel):
    """One Windows logon session, as the agent enumerated it via the WTS APIs.

    `state` and `connection` are Literals rather than free strings: the agent already
    narrowed Windows' nine connect-states down to the two that mean a person has a desktop,
    and anything else arriving here means an agent and a backend that disagree about what a
    session is. Rejecting the push is better than storing a state nothing can render.
    """
    session_id: int = Field(ge=0)
    username: str | None = Field(default=None, max_length=150)
    state: Literal["active", "disconnected"]
    connection: Literal["console", "rdp"]
    station: str | None = Field(default=None, max_length=60)
    client_name: str | None = Field(default=None, max_length=120)
    logon_at: datetime | None = None
    idle_seconds: int | None = Field(default=None, ge=0)


class HardwareInfo(BaseModel):
    manufacturer: str | None = Field(default=None, max_length=150)
    model: str | None = Field(default=None, max_length=150)
    cpu_name: str | None = Field(default=None, max_length=200)
    total_ram_mb: int | None = Field(default=None, ge=0)
    total_storage_gb: float | None = Field(default=None, ge=0)


class TelemetryPush(BaseModel):
    """Single payload the agent sends each cycle."""

    collected_at: datetime

    # Metrics — always present
    cpu_percent: float = Field(ge=0, le=100)
    ram_total_mb: int = Field(gt=0)
    ram_used_mb: int = Field(ge=0)
    disks: list[DiskInfo]

    # Inventory — sent periodically (agent may omit if unchanged)
    hardware: HardwareInfo | None = None
    event_logs: list[EventLogEntry] = []
    installed_apps: list[InstalledAppEntry] = []
    services: list[ServiceEntry] = []
    windows_updates: list[WindowsUpdateEntry] = []

    # Logon sessions. Unlike the inventory above this is sent on EVERY push, because the
    # Sessions view is only worth having if it is current — an hourly session list would
    # show people at desks they left 50 minutes ago.
    #
    # `None` and `[]` are deliberately different. None means "this agent build does not
    # report sessions", and the stored rows are left alone; an empty list means "this
    # machine genuinely has nobody signed in", and the rows are cleared. Collapsing the two
    # would make every device look deserted the moment an old agent checked in.
    sessions: list[SessionEntry] | None = None


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
    state: str
    error_code: str | None
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
