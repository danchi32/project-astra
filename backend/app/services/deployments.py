"""A4 — push software to chosen devices, and see where it landed.

A deployment resolves its targets (devices + groups, minus exclusions) once, at creation —
a snapshot, so a device added to the group tomorrow is not silently included in yesterday's
push — and creates one ordinary remediation task per device through the normal path.
Offline devices pick their task up when they next check in. The fleet circuit breaker still
applies: a push bigger than it allows stops, and says how far it got.
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, RemediationSource, RemediationTask, User
from app.models.deployment import Deployment
from app.models.grouping import DeviceGroupMember
from app.services.audit import AuditService
from app.services.exceptions import NotFoundError, ValidationError
from app.services.remediation.service import (
    AlreadyQueuedError,
    RemediationError,
    RemediationService,
)
from app.services.software_catalog import CATALOG

MAX_TARGETS = 1000


class DeploymentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def resolve_targets(self, org_id, device_ids, group_ids, exclude_ids) -> list[Device]:
        wanted = set(device_ids)
        if group_ids:
            wanted |= set((await self.session.execute(
                select(DeviceGroupMember.device_id).where(DeviceGroupMember.group_id.in_(group_ids))
            )).scalars())
        wanted -= set(exclude_ids)
        if not wanted:
            return []
        # Org-scoped here, not trusted from the ids: a group id or device id from another org
        # resolves to nothing.
        return list((await self.session.execute(
            select(Device).where(Device.org_id == org_id, Device.id.in_(wanted),
                                 Device.is_active.is_(True)).order_by(Device.hostname)
        )).scalars())

    async def create_install(
        self, *, actor: User, package_id: str, device_ids: list[uuid.UUID],
        group_ids: list[uuid.UUID], exclude_ids: list[uuid.UUID], reason: str,
    ) -> tuple[Deployment, dict[str, int], str | None]:
        item = CATALOG.get(package_id)
        if item is None:
            raise ValidationError(f"'{package_id}' is not in the software catalog.")
        devices = await self.resolve_targets(actor.org_id, device_ids, group_ids, exclude_ids)
        if not devices:
            raise ValidationError("No devices selected (after exclusions).")
        if len(devices) > MAX_TARGETS:
            raise ValidationError(f"At most {MAX_TARGETS} devices per push.")

        dep = Deployment(
            org_id=actor.org_id, action_id="install_package", params={"package_id": package_id},
            title=f"Install {item.name}", reason=reason, created_by_user_id=actor.id,
            targets={"device_ids": [str(i) for i in device_ids],
                     "group_ids": [str(i) for i in group_ids],
                     "exclude_device_ids": [str(i) for i in exclude_ids]},
        )
        self.session.add(dep)
        await self.session.flush()          # dep.id exists only after a flush
        await AuditService(self.session).record(
            org_id=actor.org_id, actor_id=actor.id, action="deployment.create",
            target_type="deployment", target_id=str(dep.id),
            detail={"package": package_id, "devices": len(devices)},
        )
        await self.session.commit()

        svc = RemediationService(self.session)
        counts = {"queued": 0, "already_running": 0, "failed": 0, "not_attempted": 0}
        error = None
        for i, device in enumerate(devices):
            try:
                await svc.create_task(
                    org_id=actor.org_id, device=device, action_id="install_package",
                    params={"package_id": package_id}, reason=reason,
                    source=RemediationSource.USER, actor_user_id=actor.id, approver=actor,
                    deployment_id=dep.id,
                )
                counts["queued"] += 1
            except AlreadyQueuedError:
                counts["already_running"] += 1
            except RemediationError as exc:
                counts["failed"] += 1
                error = str(exc)
                if "safety limit" in error.lower():
                    counts["not_attempted"] = len(devices) - i - 1
                    break
        return dep, counts, error

    async def list(self, *, actor: User, limit: int = 50) -> list[tuple[Deployment, dict[str, int]]]:
        deps = list((await self.session.execute(
            select(Deployment).where(Deployment.org_id == actor.org_id)
            .order_by(Deployment.created_at.desc()).limit(limit)
        )).scalars())
        rollup: dict[uuid.UUID, dict[str, int]] = {d.id: {} for d in deps}
        if deps:
            for dep_id, status, n in (await self.session.execute(
                select(RemediationTask.deployment_id, RemediationTask.status, func.count())
                .where(RemediationTask.deployment_id.in_(rollup.keys()))
                .group_by(RemediationTask.deployment_id, RemediationTask.status)
            )).all():
                rollup[dep_id][status.value] = n
        return [(d, rollup[d.id]) for d in deps]

    async def get(self, *, actor: User, deployment_id: uuid.UUID):
        dep = await self.session.get(Deployment, deployment_id)
        if dep is None or dep.org_id != actor.org_id:
            raise NotFoundError("Deployment not found")
        rows = (await self.session.execute(
            select(RemediationTask, Device.hostname)
            .join(Device, Device.id == RemediationTask.device_id)
            .where(RemediationTask.deployment_id == dep.id)
            .order_by(Device.hostname)
        )).all()
        return dep, rows
