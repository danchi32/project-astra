import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import RemoteSessionStatus
from app.services.remote_control import MIN_REASON_LENGTH


class RemoteSessionRequest(BaseModel):
    device_id: uuid.UUID
    # Validated here as well as in the service, so a caller gets a 422 naming the field
    # rather than a 400 naming nothing. The service keeps its own check because it is
    # reachable from places that are not this endpoint.
    reason: str = Field(min_length=MIN_REASON_LENGTH, max_length=500)


class RemoteSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    device_id: uuid.UUID
    device_hostname: str | None = None
    requested_by_user_id: uuid.UUID
    requested_by_name: str | None = None
    reason: str
    status: RemoteSessionStatus
    requested_at: datetime
    responded_at: datetime | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: int | None = None

    #: Only ever present once the person at the device has agreed, and only for the
    #: technician who asked. It carries a credential, so it is minted per request and
    #: never stored — see the endpoint for why it is not on the row.
    viewer_url: str | None = None

    #: What the portal should say while `status` is pending. Sent by the server so the
    #: countdown the technician watches is the same one the sweep enforces.
    expires_in_seconds: int | None = None
