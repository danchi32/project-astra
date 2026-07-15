import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import SubscriptionStatus


class OrganizationAdminRead(BaseModel):
    """An organization as the platform operator sees it — status + usage."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    plan: str
    subscription_status: SubscriptionStatus
    trial_ends_at: datetime | None
    current_period_end: datetime | None
    created_at: datetime
    user_count: int = 0
    device_count: int = 0


class RemediationActionOption(BaseModel):
    """A remediation action the operator can attach to a global fix."""
    id: str
    label: str
    tier: str
    params: list[str] = []


class GlobalFixCreate(BaseModel):
    """A global auto-apply fix: when any org's user reports a matching problem,
    `action_id` is applied automatically (no LLM call)."""
    problem: str = Field(min_length=1, max_length=1000)
    action_id: str = Field(min_length=1)
    process_name: str | None = Field(default=None, max_length=100)  # for restart_application
    service_name: str | None = Field(default=None, max_length=100)  # for restart_service


class GlobalFixRead(BaseModel):
    id: uuid.UUID
    problem: str
    action_id: str
    action_label: str
    params: dict | None
    created_at: datetime


class OrganizationUpdate(BaseModel):
    """Operator actions: change plan/status, set a renewal date, or extend the
    trial by N days (a convenience that bumps trial_ends_at from now)."""
    plan: str | None = Field(default=None, max_length=40)
    subscription_status: SubscriptionStatus | None = None
    trial_ends_at: datetime | None = None
    current_period_end: datetime | None = None
    extend_trial_days: int | None = Field(default=None, ge=1, le=365)
