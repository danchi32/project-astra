import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import RemediationSource, User, UserRole
from app.schemas.remediation import (
    RemediationActionRead,
    RemediationCreate,
    RemediationTaskRead,
)
from app.services.exceptions import NotFoundError
from app.services.remediation.actions import ACTIONS
from app.services.remediation.service import RemediationError, RemediationService

router = APIRouter(prefix="/remediations", tags=["remediation"])

staff_required = require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)


@router.get("/actions", response_model=list[RemediationActionRead], summary="List remediation actions")
async def list_actions(_: User = Depends(get_current_user)) -> list[RemediationActionRead]:
    return [
        RemediationActionRead(
            id=a.id, label=a.label, tier=a.tier.value, description=a.description,
            params=list(a.params),
        )
        for a in ACTIONS.values()
    ]


@router.get("", response_model=list[RemediationTaskRead], summary="List remediation tasks")
async def list_tasks(
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> list[RemediationTaskRead]:
    rows = await RemediationService(session).list_for_org(actor=actor)
    return [RemediationTaskRead.model_validate(t) for t in rows]


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
        )
    except RemediationError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return RemediationTaskRead.model_validate(task)


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
    return RemediationTaskRead.model_validate(task)


@router.post("/{task_id}/reject", response_model=RemediationTaskRead, summary="Reject a pending task")
async def reject_task(
    task_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> RemediationTaskRead:
    task = await RemediationService(session).reject_task(actor=actor, task_id=task_id)
    return RemediationTaskRead.model_validate(task)
