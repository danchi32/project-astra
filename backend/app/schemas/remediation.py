import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import RemediationSource, RemediationStatus


class RemediationActionRead(BaseModel):
    id: str
    label: str
    tier: str
    description: str
    params: list[str]


class RemediationTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    device_id: uuid.UUID
    device_hostname: str | None = None
    action_id: str
    action_label: str | None = None
    params: dict[str, Any] | None
    tier: str
    status: RemediationStatus
    reason: str
    source: RemediationSource
    requested_by_user_id: uuid.UUID | None
    approved_by_user_id: uuid.UUID | None
    result: dict[str, Any] | None
    created_at: datetime
    completed_at: datetime | None


class RemediationCreate(BaseModel):
    device_id: uuid.UUID
    action_id: str
    params: dict[str, Any] | None = None
    reason: str = Field(min_length=1, max_length=1000)


# ── Agent-facing (device) ──────────────────────────────────────────────────

class AgentRemediationTask(BaseModel):
    """A task dispatched to the agent for execution."""

    id: uuid.UUID
    action_id: str
    params: dict[str, Any] | None


class AgentRemediationResult(BaseModel):
    success: bool
    output: str = Field(default="", max_length=4000)
