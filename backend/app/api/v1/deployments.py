"""A2 + A4 — software catalog and multi-device pushes."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.database import get_db
from app.models import User, UserRole
from app.services.deployments import DeploymentService
from app.services.remediation.service import RemediationError
from app.services.software_catalog import CATALOG

router = APIRouter(tags=["software"])

# Pushing software is approval-tier work: technicians and admins, the same people who may
# approve it on a single device.
staff_required = require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)


class CatalogItemRead(BaseModel):
    package_id: str
    name: str
    publisher: str
    category: str


class InstallRequest(BaseModel):
    package_id: str = Field(max_length=100)
    device_ids: list[uuid.UUID] = Field(default_factory=list, max_length=1000)
    group_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    exclude_device_ids: list[uuid.UUID] = Field(default_factory=list, max_length=1000)
    reason: str = Field(min_length=3, max_length=500)
    # C2: one device, then 10%, then the rest, with a health gate between. On unless the
    # pusher turns it off; a one-device push is a single wave either way.
    canary: bool = True


class HaltRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=200)


class DeploymentSummary(BaseModel):
    id: uuid.UUID
    title: str
    reason: str
    created_at: datetime
    status_counts: dict[str, int]
    # C2. waves_total None = all at once. current_wave is 1-based for display.
    waves_total: int | None = None
    current_wave: int | None = None
    waiting: int = 0
    halted_at: datetime | None = None
    halt_reason: str | None = None


class DeploymentCreated(DeploymentSummary):
    queued: int
    already_running: int
    failed: int
    not_attempted: int
    error: str | None = None


def _waves(dep) -> dict:
    if not dep.waves:
        return {"halted_at": dep.halted_at, "halt_reason": dep.halt_reason}
    return {"waves_total": len(dep.waves), "current_wave": dep.current_wave + 1,
            "waiting": sum(len(w) for w in dep.waves[dep.current_wave + 1:]),
            "halted_at": dep.halted_at, "halt_reason": dep.halt_reason}


class DeploymentDeviceRow(BaseModel):
    device_id: uuid.UUID
    hostname: str
    status: str
    message: str | None
    completed_at: datetime | None


class DeploymentDetail(DeploymentSummary):
    devices: list[DeploymentDeviceRow]


def _message(task) -> str | None:
    out = (task.result or {}).get("output") if isinstance(task.result, dict) else None
    return (out or "")[:300] or None


@router.get("/software/catalog", response_model=list[CatalogItemRead],
            summary="Software SAVIO can install (server-side allowlist)")
async def software_catalog(_: User = Depends(staff_required)) -> list[CatalogItemRead]:
    return [CatalogItemRead(package_id=i.winget_id, name=i.name, publisher=i.publisher,
                            category=i.category)
            for i in sorted(CATALOG.values(), key=lambda i: (i.category, i.name))]


@router.post("/deployments/install", response_model=DeploymentCreated,
             status_code=status.HTTP_201_CREATED,
             summary="Install one catalog package on chosen devices and groups (staff; audited)")
async def create_install(
    body: InstallRequest,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> DeploymentCreated:
    dep, counts, error = await DeploymentService(session).create_install(
        actor=actor, package_id=body.package_id, device_ids=body.device_ids,
        group_ids=body.group_ids, exclude_ids=body.exclude_device_ids, reason=body.reason,
        canary=body.canary,
    )
    counts.pop("waiting", None)
    return DeploymentCreated(id=dep.id, title=dep.title, reason=dep.reason,
                             created_at=dep.created_at, status_counts={}, error=error,
                             **counts, **_waves(dep))


@router.get("/deployments", response_model=list[DeploymentSummary],
            summary="Recent software pushes with a status count each (staff)")
async def list_deployments(
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> list[DeploymentSummary]:
    return [DeploymentSummary(id=d.id, title=d.title, reason=d.reason, created_at=d.created_at,
                              status_counts=c, **_waves(d))
            for d, c in await DeploymentService(session).list(actor=actor)]


@router.get("/deployments/{deployment_id}", response_model=DeploymentDetail,
            summary="One push, device by device (staff)")
async def get_deployment(
    deployment_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> DeploymentDetail:
    dep, rows = await DeploymentService(session).get(actor=actor, deployment_id=deployment_id)
    counts: dict[str, int] = {}
    devices = []
    for task, hostname in rows:
        counts[task.status.value] = counts.get(task.status.value, 0) + 1
        devices.append(DeploymentDeviceRow(device_id=task.device_id, hostname=hostname,
                                           status=task.status.value, message=_message(task),
                                           completed_at=task.completed_at))
    return DeploymentDetail(id=dep.id, title=dep.title, reason=dep.reason,
                            created_at=dep.created_at, status_counts=counts, devices=devices,
                            **_waves(dep))


@router.post("/deployments/{deployment_id}/halt", response_model=DeploymentSummary,
             summary="Stop a rollout: no further waves, queued installs cancelled (staff; audited)")
async def halt_deployment(
    deployment_id: uuid.UUID,
    body: HaltRequest,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> DeploymentSummary:
    dep = await DeploymentService(session).halt_by(actor=actor, deployment_id=deployment_id,
                                                   reason=body.reason)
    return DeploymentSummary(id=dep.id, title=dep.title, reason=dep.reason,
                             created_at=dep.created_at, status_counts={}, **_waves(dep))


@router.post("/deployments/{deployment_id}/resume", response_model=DeploymentSummary,
             summary="Resume a halted rollout and release its next wave now (staff; audited)")
async def resume_deployment(
    deployment_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> DeploymentSummary:
    try:
        dep = await DeploymentService(session).resume(actor=actor, deployment_id=deployment_id)
    except RemediationError as exc:
        # The resumer may not approve this action themselves (org policy / tier).
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return DeploymentSummary(id=dep.id, title=dep.title, reason=dep.reason,
                             created_at=dep.created_at, status_counts={}, **_waves(dep))
