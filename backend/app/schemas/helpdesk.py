from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.support.freshservice import normalise_domain


class HelpdeskSettingsRead(BaseModel):
    """What the portal shows. Never the credential.

    `api_key_masked` exists so an administrator can tell WHICH key is saved without being
    able to use it — the difference between "is this configured" and "here is the secret".
    """

    model_config = ConfigDict(from_attributes=True)

    provider: str = "freshservice"
    enabled: bool = False
    domain: str | None = None
    api_key_masked: str = ""
    default_priority: int = 1
    default_source: int | None = None
    workspace_id: int | None = None
    group_id: int | None = None
    category_map: dict[str, Any] | None = None
    last_error: str | None = None
    last_verified_at: datetime | None = None
    # True only when everything needed to actually file a ticket is present. The portal
    # uses this rather than `enabled`, because a half-filled form is not a connection.
    ready: bool = False


class HelpdeskSettingsUpdate(BaseModel):
    """A partial update — finance and IT fill this in over more than one sitting, so an
    omitted field must not blank what is already there."""

    provider: Literal["freshservice"] | None = None
    enabled: bool | None = None
    domain: str | None = Field(default=None, max_length=120)
    # Write-only. Sent when it changes; omitted the rest of the time.
    api_key: str | None = Field(default=None, max_length=200)
    default_priority: int | None = Field(default=None, ge=1, le=4)
    default_source: int | None = Field(default=None, ge=1)
    workspace_id: int | None = Field(default=None, ge=1)
    group_id: int | None = Field(default=None, ge=1)
    category_map: dict[str, Any] | None = None

    @field_validator("domain")
    @classmethod
    def _bare_subdomain(cls, value: str | None) -> str | None:
        """Accept whatever an admin pastes from their address bar — and nothing else.

        The rule lives with the code that builds the URL, so the two can't drift apart:
        a subdomain this accepts but `base_url` mis-handles is an SSRF.
        """
        if value is None or not value.strip():
            return None
        return normalise_domain(value)


class HelpdeskVerifyResult(BaseModel):
    ok: bool
    detail: str | None = None
