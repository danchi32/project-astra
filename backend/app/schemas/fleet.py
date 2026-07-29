import uuid

from pydantic import BaseModel, Field


class FleetAffected(BaseModel):
    device_id: uuid.UUID
    hostname: str


class FleetIssue(BaseModel):
    """One problem seen across the fleet, with every device it affects and — where a safe
    remediation exists — the action that fixes it on all of them at once."""
    key: str
    category: str          # "compliance" | "update"
    title: str
    detail: str = ""
    severity: str          # "high" | "medium" | "low"
    fix_action_id: str | None = None
    fix_params: dict[str, str] | None = None
    affected: list[FleetAffected]


class FleetIssuesResponse(BaseModel):
    issues: list[FleetIssue]


class BulkRemediateRequest(BaseModel):
    device_ids: list[uuid.UUID] = Field(min_length=1, max_length=1000)
    action_id: str = Field(min_length=1, max_length=100)
    params: dict[str, str] | None = None
    reason: str = Field(min_length=1, max_length=1000)


class BulkRemediateResult(BaseModel):
    queued: int
    failed: int
    error: str | None = None
