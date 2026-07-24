from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# Absolute security floor — an org may raise the minimum password length above this
# but never below it, regardless of what is submitted.
PASSWORD_FLOOR = 8


class OrganizationSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    org_name: str
    auto_approve_automatic: bool
    require_admin_for_approval_tier: bool
    min_password_length: int
    enrollment_token_default_days: int
    updated_at: datetime


class OrganizationSettingsUpdate(BaseModel):
    """PATCH — only provided fields change."""

    org_name: str | None = Field(default=None, min_length=1, max_length=200)
    auto_approve_automatic: bool | None = None
    require_admin_for_approval_tier: bool | None = None
    min_password_length: int | None = Field(default=None, ge=PASSWORD_FLOOR, le=128)
    enrollment_token_default_days: int | None = Field(default=None, ge=1, le=90)


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=PASSWORD_FLOOR, max_length=72)


# A single role's capabilities across the platform — reference matrix for the
# Settings → Permissions view. Reflects the RBAC actually enforced in the API.
class RolePermissions(BaseModel):
    role: str
    label: str
    description: str
    capabilities: dict[str, bool]


class PermissionMatrix(BaseModel):
    # Ordered list of capability keys → human labels, so the UI can render columns.
    capabilities: list[dict[str, str]]
    roles: list[RolePermissions]
