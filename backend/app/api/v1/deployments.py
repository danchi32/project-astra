"""A2 + A4 — software catalog and multi-device pushes."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.database import get_db
from app.models import User, UserRole
from app.services.deployments import DeploymentService
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


class DeploymentSummary(BaseModel):
    id: uuid.UUID
    title: str
    reason: str
    created_at: datetime
    status_counts: dict[str, int]


class DeploymentCreated(DeploymentSummary):
    queued: int
    already_running: int
    failed: int
    not_attempted: int
    error: str | None = None


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
    )
    return DeploymentCreated(id=dep.id, title=dep.title, reason=dep.reason,
                             created_at=dep.created_at, status_counts={}, error=error, **counts)


@router.get("/deployments", response_model=list[DeploymentSummary],
            summary="Recent software pushes with a status count each (staff)")
async def list_deployments(
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> list[DeploymentSummary]:
    return [DeploymentSummary(id=d.id, title=d.title, reason=d.reason, created_at=d.created_at,
                              status_counts=c)
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
                            created_at=dep.created_at, status_counts=counts, devices=devices)
