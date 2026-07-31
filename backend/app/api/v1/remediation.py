import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import RemediationSource, RemediationStatus, User, UserRole
from app.schemas.pagination import DEFAULT_PAGE_SIZE, Page, build, clamp
from app.schemas.remediation import (
    RemediationActionRead,
    RemediationCreate,
    RemediationTaskRead,
)
from app.services.exceptions import NotFoundError
from app.services.remediation.actions import ACTIONS
from app.services.remediation.service import (
    AlreadyQueuedError,
    RemediationError,
    RemediationService,
)

router = APIRouter(prefix="/remediations", tags=["remediation"])

staff_required = require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)


def _enrich(task, hostname_by_id: dict) -> RemediationTaskRead:
    read = RemediationTaskRead.model_validate(task)
    read.device_hostname = hostname_by_id.get(task.device_id)
    action = ACTIONS.get(task.action_id)
    read.action_label = action.label if action else task.action_id
    return read


@router.get("/actions", response_model=list[RemediationActionRead], summary="List remediation actions")
async def list_actions(_: User = Depends(get_current_user)) -> list[RemediationActionRead]:
    return [
        RemediationActionRead(
            id=a.id, label=a.label, tier=a.tier.value, description=a.description,
            params=list(a.params),
        )
        for a in ACTIONS.values()
    ]


@router.get("", response_model=Page[RemediationTaskRead], summary="List remediation tasks")
async def list_tasks(
    device_id: uuid.UUID | None = None,
    status: list[RemediationStatus] | None = Query(default=None),
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> Page[RemediationTaskRead]:
    """`device_id` narrows to one machine in the database.

    `status` is repeatable so a screen showing "awaiting approval" and "history" as separate
    tables asks for each separately. Splitting one page of results in the browser would make
    "Awaiting approval (3)" mean "3 on this page", which is not what anyone reads it as.
    """
    from app.repositories.devices import DeviceRepository

    page, page_size = clamp(page, page_size)
    rows, total = await RemediationService(session).list_page(
        actor=actor, device_id=device_id, status=status,
        offset=(page - 1) * page_size, limit=page_size,
    )
    hostname_by_id = await DeviceRepository(session).hostnames_for(
        actor.org_id, {r.device_id for r in rows}
    )
    return build([_enrich(t, hostname_by_id) for t in rows], total, page, page_size)


@router.get("/summary", response_model=dict[str, int], summary="Task counts by status")
async def remediation_summary(
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    from app.repositories.remediation import RemediationRepository

    return await RemediationRepository(session).count_by_status(actor.org_id)


@router.post(
    "", response_model=RemediationTaskRead, status_code=status.HTTP_201_CREATED,
    summary="Manually create a remediation task on a device (staff)",
)
async def create_task(
    body: RemediationCreate,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> RemediationTaskRead:
    from app.repositories.devices import DeviceRepository

    device = await DeviceRepository(session).get(body.device_id)
    if device is None or device.org_id != actor.org_id:
        raise NotFoundError("Device not found")
    try:
        task = await RemediationService(session).create_task(
            org_id=actor.org_id, device=device, action_id=body.action_id,
            params=body.params, reason=body.reason,
            source=RemediationSource.USER, actor_user_id=actor.id,
            # The portal's "Run a fix" is a deliberate choice by someone who may approve it,
            # so it clears in the same call. Role checks still apply inside the service.
            approver=actor if body.approve else None,
        )
    except AlreadyQueuedError as exc:
        from fastapi import HTTPException
        # 409, not 400: the request was well-formed and the caller wants something that is
        # already happening. The portal shows this as "already running", not as an error.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except RemediationError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _enrich(task, {device.id: device.hostname})


@router.post("/{task_id}/approve", response_model=RemediationTaskRead, summary="Approve a pending task")
async def approve_task(
    task_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> RemediationTaskRead:
    try:
        task = await RemediationService(session).approve_task(actor=actor, task_id=task_id)
    except RemediationError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return _enrich(task, await _hostname_map(session, task))


@router.post("/{task_id}/reject", response_model=RemediationTaskRead, summary="Reject a pending task")
async def reject_task(
    task_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> RemediationTaskRead:
    task = await RemediationService(session).reject_task(actor=actor, task_id=task_id)
    return _enrich(task, await _hostname_map(session, task))


async def _hostname_map(session: AsyncSession, task) -> dict:
    from app.repositories.devices import DeviceRepository

    device = await DeviceRepository(session).get(task.device_id)
    return {device.id: device.hostname} if device else {}
