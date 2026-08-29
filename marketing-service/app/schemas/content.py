import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.content import ContentChannel, ContentEventType, ContentStatus


class DraftRequest(BaseModel):
    channel: ContentChannel
    brief: str = Field(min_length=10, max_length=4000,
                       description="What to write. The more specific, the less invention.")
    campaign: str | None = Field(default=None, max_length=160)


class ReviseRequest(BaseModel):
    feedback: str = Field(min_length=1, max_length=4000)
    #: Who asked. Recorded on the event — an approval trail with no names in it is a log,
    #: not a trail.
    actor: str = Field(min_length=1, max_length=160)


class ApproveRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=160)
    #: Which version. Required, never inferred: approving "the item" is how a reviewer
    #: ends up having endorsed something that arrived after they looked.
    version_id: uuid.UUID


class SimpleActorRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=160)


class PublishedRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=160)
    url: str | None = Field(default=None, max_length=1000)
    ref: str | None = Field(default=None, max_length=200)


class ScheduleRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=160)
    when: datetime


class VersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_number: int
    created_at: datetime
    headline: str | None
    body: str
    hashtags: str | None
    cta: str | None
    media_url: str | None
    authored_by: str | None
    revision_reason: str | None
    check_result: dict | None


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    event: ContentEventType
    actor: str
    version_id: uuid.UUID | None
    note: str | None


class ContentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    channel: ContentChannel
    campaign: str | None
    brief: str | None
    status: ContentStatus
    current_version_id: uuid.UUID | None
    approved_version_id: uuid.UUID | None
    approved_by: str | None
    approved_at: datetime | None
    scheduled_for: datetime | None
    published_at: datetime | None
    published_url: str | None


class ContentDetail(ContentRead):
    versions: list[VersionRead] = []
    events: list[EventRead] = []
