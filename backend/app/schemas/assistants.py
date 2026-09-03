import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.models import AssistantVersionStatus


class AssistantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class AssistantUpdate(BaseModel):
    """Identity only. Behaviour is never edited here — it belongs to a version."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class AssistantVersionCreate(BaseModel):
    """Every field optional: an omitted field means "use the server default", which is how
    a version that reproduces today's ASTRA behaviour is expressed."""

    system_prompt: str | None = Field(default=None, max_length=20000)
    model: str | None = Field(default=None, max_length=60)
    max_tokens: int | None = Field(default=None, ge=256, le=200_000)
    max_tool_iterations: int | None = Field(default=None, ge=1, le=20)
    # None → every tool the engine advertises. [] → this assistant may call nothing.
    tool_ids: list[str] | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("max_tool_iterations")
    @classmethod
    def _may_lower_but_not_raise(cls, value: int | None) -> int | None:
        """Each iteration is a billed model call.

        A cap a tenant can raise is a tenant-writable multiplier on the AI bill, so the
        server setting is a ceiling and this field can only come in under it. Raising it for
        everyone is an operator decision — `ASTRA_AI_MAX_TOOL_ITERATIONS`.
        """
        from app.core.config import get_settings

        ceiling = get_settings().ai_max_tool_iterations
        if value is not None and value > ceiling:
            raise ValueError(
                f"max_tool_iterations may not exceed the server limit of {ceiling}. "
                "A version can use fewer steps than the platform allows, never more."
            )
        return value

    @field_validator("model", "max_tokens")
    @classmethod
    def _not_yet_honoured(cls, value: object, info: ValidationInfo) -> object:
        """Refuse rather than accept and ignore.

        The engine does not build the provider — `ConversationService._route` does, choosing
        between the free built-in paths and the real LLM on cost — so a per-version model is
        not wired yet. Accepting the field and silently doing nothing with it is the worse
        failure: someone sets a cheaper model, sees no change in the bill, and has no way to
        tell whether the platform ignored them or the model is simply not cheaper.
        """
        if value is not None:
            raise ValueError(
                f"'{info.field_name}' is not configurable yet — every assistant runs on the "
                "organization's server-configured model. Leave it unset."
            )
        return value


class AssistantVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_no: int
    status: AssistantVersionStatus
    system_prompt: str | None = None
    model: str | None = None
    max_tokens: int | None = None
    max_tool_iterations: int | None = None
    tool_ids: list[str] | None = None
    notes: str | None = None
    created_by_user_id: uuid.UUID | None = None
    created_at: datetime


class AssistantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    published_version_id: uuid.UUID | None = None
    archived: bool
    created_at: datetime
    # True for the platform's own assistants (org_id NULL). Tenants may read and copy these
    # but never edit them, and the portal needs to know that without seeing org_id.
    builtin: bool = False


class AssistantDetail(AssistantRead):
    versions: list[AssistantVersionRead] = []
