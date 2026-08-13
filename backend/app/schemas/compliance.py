import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CheckStatus = Literal["pass", "fail", "unknown"]
DeviceComplianceStatus = Literal["compliant", "at_risk", "non_compliant", "unknown"]


class BannedSoftwareCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class BannedSoftwareRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    pattern: str
    created_at: datetime


class CheckResult(BaseModel):
    key: str
    label: str
    status: CheckStatus
    detail: str
    # The remediation an admin can push to fix this check, if one applies.
    fix_action_id: str | None = None


class DeviceCompliance(BaseModel):
    device_id: uuid.UUID
    hostname: str
    status: DeviceComplianceStatus
    score: int  # 0–100, over the device's *known* checks
    passed: int
    failed: int
    checks: list[CheckResult]
    # The device's reported USB storage state; None until a reporting agent has beaten.
    usb_storage_blocked: bool | None = None


class CheckBreakdown(BaseModel):
    key: str
    label: str
    passed: int
    failed: int
    unknown: int


class UsbPosture(BaseModel):
    """How USB mass storage sits across the fleet, from what each agent last reported.
    `unknown` is devices no agent new enough to report it has checked in for yet."""
    blocked: int
    allowed: int
    unknown: int


class ComplianceSummary(BaseModel):
    total_devices: int
    compliant: int
    at_risk: int
    non_compliant: int
    unknown: int
    score: int  # fleet compliance % = compliant / total
    checks: list[CheckBreakdown]
    usb: UsbPosture
