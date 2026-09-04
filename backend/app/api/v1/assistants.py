import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import Assistant, User, UserRole
from app.schemas.assistants import (
    AssistantCreate,
    AssistantDetail,
    AssistantRead,
    AssistantUpdate,
    AssistantVersionCreate,
    AssistantVersionRead,
    ToolSummary,
)
from app.services.ai.tools import TOOL_SCHEMAS
from app.services.assistants import AssistantService

router = APIRouter(prefix="/assistants", tags=["assistants"])

staff_required = require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)


def _read(row: Assistant) -> AssistantRead:
    """`builtin` is derived from org_id, which never leaves the server."""
    return AssistantRead(
        id=row.id, name=row.name, description=row.description,
        published_version_id=row.published_version_id, archived=row.archived,
        created_at=row.created_at, builtin=row.org_id is None,
    )


@router.get("", response_model=list[AssistantRead], summary="List assistants")
async def list_assistants(
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[AssistantRead]:
    rows = await AssistantService(session).list_for_org(org_id=actor.org_id)
    return [_read(r) for r in rows]


@router.get("/tools", response_model=list[ToolSummary], summary="Tools an assistant may be granted")
async def list_tools(actor: User = Depends(get_current_user)) -> list[ToolSummary]:
    """The grantable tool catalogue, read from the schemas the engine actually advertises.

    Declared before `/{assistant_id}` or FastAPI would try to parse "tools" as a UUID.

    It exists so the portal never hardcodes tool names. A hand-maintained copy of this list
    is the same failure that ships a marketing page describing an older product — it goes
    stale the first time a tool is added, and nothing says so.

    Escalation's two tools are included even though the engine adds them per-organization:
    a grant that omits them silently turns escalation off for that assistant, so they have
    to be visible to whoever is choosing.
    """
    from app.services.ai import escalation_tools

    return [
        ToolSummary(name=t["name"], description=t["description"])
        for t in (*TOOL_SCHEMAS, *escalation_tools.TOOL_SCHEMAS)
    ]


@router.post(
    "", response_model=AssistantRead, status_code=status.HTTP_201_CREATED,
    summary="Create an assistant (staff)",
)
async def create_assistant(
    body: AssistantCreate,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> AssistantRead:
    row = await AssistantService(session).create(
        actor=actor, name=body.name, description=body.description
    )
    return _read(row)


@router.get("/{assistant_id}", response_model=AssistantDetail, summary="Assistant detail")
async def get_assistant(
    assistant_id: uuid.UUID,
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AssistantDetail:
    service = AssistantService(session)
    row = await service.get(org_id=actor.org_id, assistant_id=assistant_id)
    versions = await service.versions(assistant_id=row.id)
    return AssistantDetail(
        **_read(row).model_dump(),
        versions=[AssistantVersionRead.model_validate(v) for v in versions],
    )


@router.patch("/{assistant_id}", response_model=AssistantRead, summary="Rename an assistant (staff)")
async def update_assistant(
    assistant_id: uuid.UUID,
    body: AssistantUpdate,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> AssistantRead:
    row = await AssistantService(session).update(
        actor=actor, assistant_id=assistant_id,
        name=body.name, description=body.description,
    )
    return _read(row)


@router.delete(
    "/{assistant_id}", status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive an assistant (staff)",
)
async def archive_assistant(
    assistant_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> None:
    await AssistantService(session).archive(actor=actor, assistant_id=assistant_id)


@router.post(
    "/{assistant_id}/versions", response_model=AssistantVersionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a draft version (staff)",
)
async def create_version(
    assistant_id: uuid.UUID,
    body: AssistantVersionCreate,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> AssistantVersionRead:
    row = await AssistantService(session).create_version(
        actor=actor, assistant_id=assistant_id, **body.model_dump()
    )
    return AssistantVersionRead.model_validate(row)


@router.patch(
    "/{assistant_id}/versions/{version_id}", response_model=AssistantVersionRead,
    summary="Edit a draft version (staff)",
)
async def update_version(
    assistant_id: uuid.UUID,
    version_id: uuid.UUID,
    body: AssistantVersionCreate,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> AssistantVersionRead:
    row = await AssistantService(session).update_version(
        actor=actor, assistant_id=assistant_id, version_id=version_id,
        **body.model_dump(exclude_unset=True),
    )
    return AssistantVersionRead.model_validate(row)


@router.post(
    "/{assistant_id}/versions/{version_id}/publish", response_model=AssistantRead,
    summary="Publish a version, or roll back by publishing an older one (admin)",
)
async def publish_version(
    assistant_id: uuid.UUID,
    version_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> AssistantRead:
    # The admin check lives in the service, not in a dependency: publishing is the privilege
    # boundary, and putting it beside the write keeps it in the same place as the audit entry.
    row = await AssistantService(session).publish_version(
        actor=actor, assistant_id=assistant_id, version_id=version_id
    )
    return _read(row)
