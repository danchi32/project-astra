"""Platform-operator (super-admin) API — manage ALL organizations. Every route
requires a platform admin."""
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_platform_admin
from app.core.database import get_db
from app.models import User
from app.repositories.devices import DeviceRepository
from app.repositories.remediation import RemediationRepository
from app.repositories.telemetry import TelemetryRepository
from app.repositories.users import UserRepository
from app.schemas.asset import AssetRead
from app.schemas.devices import DeviceRead
from app.schemas.knowledge import KnowledgeArticleCreate, KnowledgeArticleRead
from app.schemas.platform import (
    GlobalFixCreate,
    GlobalFixRead,
    OrganizationAdminRead,
    OrganizationUpdate,
    RemediationActionOption,
)
from app.schemas.remediation import RemediationTaskRead
from app.schemas.users import UserRead
from app.services.ai.knowledge import KnowledgeBaseService
from app.services.ai.learned import LearnedFixStore
from app.services.assets import AssetService
from app.services.exceptions import NotFoundError
from app.services.platform import PlatformService
from app.services.remediation.actions import ACTIONS


def _fix_read(entry) -> GlobalFixRead:
    action = ACTIONS.get(entry.action_id)
    return GlobalFixRead(
        id=entry.id, problem=entry.query_text, action_id=entry.action_id,
        action_label=action.label if action else entry.action_id,
        params=entry.params, created_at=entry.created_at,
    )

router = APIRouter(prefix="/platform", tags=["platform"])


def _enrich_task(task, hostname_by_id: dict) -> RemediationTaskRead:
    read = RemediationTaskRead.model_validate(task)
    read.device_hostname = hostname_by_id.get(task.device_id)
    action = ACTIONS.get(task.action_id)
    read.action_label = action.label if action else task.action_id
    return read


@router.get(
    "/organizations",
    response_model=list[OrganizationAdminRead],
    summary="List all organizations with status and usage (platform admin)",
)
async def list_organizations(
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> list[OrganizationAdminRead]:
    return await PlatformService(session).list_organizations()


@router.get(
    "/organizations/{org_id}",
    response_model=OrganizationAdminRead,
    summary="One organization's details (platform admin)",
)
async def get_organization(
    org_id: uuid.UUID,
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> OrganizationAdminRead:
    return await PlatformService(session).get_organization(org_id)


@router.get(
    "/organizations/{org_id}/users",
    response_model=list[UserRead],
    summary="An organization's users (platform admin)",
)
async def organization_users(
    org_id: uuid.UUID,
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> list[User]:
    return await UserRepository(session).list_by_org(org_id)


@router.get(
    "/organizations/{org_id}/devices",
    response_model=list[DeviceRead],
    summary="An organization's devices (platform admin)",
)
async def organization_devices(
    org_id: uuid.UUID,
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> list[DeviceRead]:
    devices = await DeviceRepository(session).list_by_org(org_id)
    counts = await TelemetryRepository(session).count_apps_by_device_for_org(org_id)
    return [DeviceRead.from_device(d, counts.get(d.id, 0)) for d in devices]


@router.get(
    "/organizations/{org_id}/remediation",
    response_model=list[RemediationTaskRead],
    summary="An organization's self-healing history (platform admin)",
)
async def organization_remediation(
    org_id: uuid.UUID,
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> list[RemediationTaskRead]:
    tasks = await RemediationRepository(session).list_by_org(org_id)
    devices = await DeviceRepository(session).list_by_org(org_id)
    hostname_by_id = {d.id: d.hostname for d in devices}
    return [_enrich_task(t, hostname_by_id) for t in tasks]


@router.get(
    "/organizations/{org_id}/assets",
    response_model=list[AssetRead],
    summary="An organization's assets (platform admin)",
)
async def organization_assets(
    org_id: uuid.UUID,
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> list[AssetRead]:
    return await AssetService(session).list_for_org(org_id=org_id)


# ── Global knowledge: problem→solution articles shared with EVERY organization ──
@router.get(
    "/knowledge",
    response_model=list[KnowledgeArticleRead],
    summary="List global knowledge articles (platform admin)",
)
async def list_global_knowledge(
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> list[KnowledgeArticleRead]:
    return await KnowledgeBaseService(session).list_global()


@router.post(
    "/knowledge",
    response_model=KnowledgeArticleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a global problem+solution applied to all organizations (platform admin)",
)
async def create_global_knowledge(
    body: KnowledgeArticleCreate,
    actor: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> KnowledgeArticleRead:
    return await KnowledgeBaseService(session).create_global(
        title=body.title, content=body.content, actor_user_id=actor.id
    )


@router.delete(
    "/knowledge/{article_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a global knowledge article (platform admin)",
)
async def delete_global_knowledge(
    article_id: uuid.UUID,
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> None:
    await KnowledgeBaseService(session).delete_global(article_id=article_id)


# ── Global auto-apply fixes: problem → remediation action, applied for every org ──
@router.get(
    "/remediation-actions",
    response_model=list[RemediationActionOption],
    summary="Remediation actions available for a global fix (platform admin)",
)
async def list_remediation_actions(
    _: User = Depends(require_platform_admin),
) -> list[RemediationActionOption]:
    return [
        RemediationActionOption(id=a.id, label=a.label, tier=a.tier.value, params=list(a.params))
        for a in ACTIONS.values()
    ]


@router.get(
    "/fixes",
    response_model=list[GlobalFixRead],
    summary="List global auto-apply fixes (platform admin)",
)
async def list_global_fixes(
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> list[GlobalFixRead]:
    return [_fix_read(e) for e in await LearnedFixStore(session).list_global()]


@router.post(
    "/fixes",
    response_model=GlobalFixRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a global auto-apply fix (platform admin)",
)
async def create_global_fix(
    body: GlobalFixCreate,
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> GlobalFixRead:
    params: dict = {}
    if body.process_name:
        params["process_name"] = body.process_name
    if body.service_name:
        params["service_name"] = body.service_name
    try:
        entry = await LearnedFixStore(session).create_global(
            problem=body.problem, action_id=body.action_id, params=params or None
        )
    except ValueError as exc:
        raise NotFoundError(str(exc))
    return _fix_read(entry)


@router.delete(
    "/fixes/{fix_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a global auto-apply fix (platform admin)",
)
async def delete_global_fix(
    fix_id: uuid.UUID,
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> None:
    try:
        await LearnedFixStore(session).delete_global(fix_id=fix_id)
    except LookupError:
        raise NotFoundError("Global fix not found")


@router.patch(
    "/organizations/{org_id}",
    response_model=OrganizationAdminRead,
    summary="Update an organization's plan/status/trial (platform admin)",
)
async def update_organization(
    org_id: uuid.UUID,
    body: OrganizationUpdate,
    actor: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> OrganizationAdminRead:
    return await PlatformService(session).update_organization(actor=actor, org_id=org_id, data=body)


@router.delete(
    "/organizations/{org_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an organization and all its data (platform admin)",
)
async def delete_organization(
    org_id: uuid.UUID,
    actor: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_db),
) -> None:
    await PlatformService(session).delete_organization(actor=actor, org_id=org_id)
