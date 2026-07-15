import uuid
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import Device
from app.models.base import as_utc, utcnow

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
    """The org's ready-to-run installer. The permanent enrollment key is already
    baked into the script — the admin just downloads and runs it."""
    enrollment_key: str
    server_url: str
    filename: str
    script: str


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


class HeartbeatResponse(BaseModel):
    status: str = "ok"


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
