import uuid
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import Device
from app.models.base import as_utc, utcnow
from app.schemas.remediation import AgentRemediationTask

# A device is online if it has reported within 3 heartbeat intervals (60s each).
ONLINE_THRESHOLD = timedelta(seconds=180)


class EnrollmentTokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    # Omit to use the organization's configured default expiry.
    expires_in_days: int | None = Field(default=None, ge=1, le=90)


class EnrollmentTokenCreated(BaseModel):
    id: uuid.UUID
    name: str
    # The raw token — returned exactly once at creation, never retrievable again.
    token: str
    expires_at: datetime


class EnrollmentTokenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime


class InstallerRead(BaseModel):
    """The org's enrollment details, shown next to the portable-bundle download. The
    permanent key is reusable across machines — no token step, no expiry."""
    enrollment_key: str
    server_url: str
    filename: str
    # Name the one-click .exe installer must be downloaded as — it reads the
    # enrollment key back out of its own filename. None when this deployment has no
    # usable .exe (not bundled, or built for a different backend), which is also the
    # portal's signal to offer only the .zip.
    exe_filename: str | None = None


class EnrollRequest(BaseModel):
    enrollment_token: str
    hostname: str = Field(min_length=1, max_length=255)
    machine_id: str = Field(min_length=1, max_length=100)
    os_version: str = Field(min_length=1, max_length=100)
    serial_number: str | None = Field(default=None, max_length=100)
    agent_version: str = Field(min_length=1, max_length=20)


class EnrollResponse(BaseModel):
    device_id: uuid.UUID
    device_token: str


class HeartbeatRequest(BaseModel):
    agent_version: str = Field(min_length=1, max_length=20)
    logged_in_user: str | None = Field(default=None, max_length=100)
    # Sent by agents that know how to report it. Optional because os_version was previously
    # written only at enrollment, so a device that feature-updates (or an agent that fixes
    # how it names the OS) would otherwise show the enrolment-day string forever.
    os_version: str | None = Field(default=None, min_length=1, max_length=100)
    # The device's actual USB mass-storage state, read from the registry. Optional: an agent
    # too old to report it omits the field, and an omitted field must never be read as
    # "allowed" — that would flip a genuinely blocked device to allowed on its next beat. The
    # ingest only writes this when it is present.
    usb_storage_blocked: bool | None = None
    # Opt-in: when true, the heartbeat response carries this device's approved
    # system-context tasks, so the elevated Service needs no separate poll.
    #
    # It MUST default to false. Claiming marks a task dispatched, so returning tasks to an
    # agent that doesn't know to read them would take the work away from the separate poller
    # it still relies on — silently breaking self-healing on every agent released before this.
    include_tasks: bool = False


class HeartbeatResponse(BaseModel):
    status: str = "ok"
    # Populated only when the request set include_tasks. Older agents don't read the
    # heartbeat body at all, so this is invisible to them.
    tasks: list[AgentRemediationTask] = Field(default_factory=list)


class AgentUpdateEnvelope(BaseModel):
    """The signed release manifest relayed to an agent. `manifest` is the exact JSON string
    that was signed (verified verbatim by the agent), `signature` its base64 RSA-SHA256
    signature. `available` is false when no update channel is configured."""
    available: bool = False
    manifest: str | None = None
    signature: str | None = None


class DeviceUpdate(BaseModel):
    is_active: bool | None = None


class DeviceRead(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    hostname: str
    machine_id: str
    os_version: str
    serial_number: str | None
    agent_version: str
    logged_in_user: str | None
    status: Literal["online", "offline"]
    last_seen_at: datetime | None
    is_active: bool
    created_at: datetime

    # Hardware asset attributes
    manufacturer: str | None
    model: str | None
    cpu_name: str | None
    total_ram_mb: int | None
    total_storage_gb: float | None
    installed_app_count: int

    @classmethod
    def from_device(cls, device: Device, installed_app_count: int = 0) -> "DeviceRead":
        online = (
            device.last_seen_at is not None
            and utcnow() - as_utc(device.last_seen_at) < ONLINE_THRESHOLD
        )
        return cls(
            id=device.id,
            org_id=device.org_id,
            hostname=device.hostname,
            machine_id=device.machine_id,
            os_version=device.os_version,
            serial_number=device.serial_number,
            agent_version=device.agent_version,
            logged_in_user=device.logged_in_user,
            status="online" if online else "offline",
            last_seen_at=device.last_seen_at,
            is_active=device.is_active,
            created_at=device.created_at,
            manufacturer=device.manufacturer,
            model=device.model,
            cpu_name=device.cpu_name,
            total_ram_mb=device.total_ram_mb,
            total_storage_gb=device.total_storage_gb,
            installed_app_count=installed_app_count,
        )


class DevicePage(BaseModel):
    """One page of a searched device list — the database does the search + paging so
    this scales to large fleets."""
    items: list[DeviceRead]
    total: int
    page: int
    page_size: int
    pages: int
