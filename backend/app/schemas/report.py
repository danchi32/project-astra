import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.asset import AssetRead, AssetSummary


class FleetHealthDeviceRow(BaseModel):
    device_id: uuid.UUID
    hostname: str
    status: Literal["online", "offline"]
    cpu_percent: float | None
    ram_percent: float | None
    disk_free_percent_min: float | None
    critical_event_count: int
    pending_update_count: int
    last_seen_at: datetime | None


class FleetHealthReport(BaseModel):
    generated_at: datetime
    total_devices: int
    online_devices: int
    offline_devices: int
    avg_cpu_percent: float
    avg_ram_percent: float
    total_critical_events: int
    total_pending_updates: int
    devices: list[FleetHealthDeviceRow]


class RemediationReportRow(BaseModel):
    task_id: uuid.UUID
    device_hostname: str | None
    action_id: str
    tier: str
    status: str
    source: str
    created_at: datetime
    completed_at: datetime | None


class RemediationReport(BaseModel):
    generated_at: datetime
    period_days: int
    total_tasks: int
    succeeded: int
    failed: int
    pending_approval: int
    success_rate: float
    by_tier: dict[str, int]
    by_action: dict[str, int]
    tasks: list[RemediationReportRow]


class AssetReport(BaseModel):
    generated_at: datetime
    summary: AssetSummary
    assets: list[AssetRead]
