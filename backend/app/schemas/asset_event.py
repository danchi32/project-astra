import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models import AssetEventType


class AssetEventRead(BaseModel):
    id: uuid.UUID
    event_type: AssetEventType
    actor_name: str | None = None   # who performed it
    user_name: str | None = None    # the assignee, for assign/acknowledge events
    from_value: str | None = None
    to_value: str | None = None
    note: str | None = None
    occurred_at: datetime


class StatusDuration(BaseModel):
    status: str
    seconds: float


class AssetPassport(BaseModel):
    """An asset's full lifecycle record — its 'passport'."""
    asset_id: uuid.UUID
    name: str
    category: str
    asset_tag: str | None = None
    serial_number: str | None = None
    current_status: str
    current_location: str | None = None
    current_holder: str | None = None
    holder_since: datetime | None = None
    acquired_at: datetime            # when the asset was registered
    age_days: int
    repair_count: int
    assignment_count: int
    time_in_status: list[StatusDuration]   # seconds spent in each status
    events: list[AssetEventRead]           # newest first
