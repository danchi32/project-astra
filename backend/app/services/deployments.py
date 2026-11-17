"""A4 — push software to chosen devices, and see where it landed. C2 — in waves.

A deployment resolves its targets (devices + groups, minus exclusions) once, at creation —
a snapshot, so a device added to the group tomorrow is not silently included in yesterday's
push — and creates one ordinary remediation task per device through the normal path.
Offline devices pick their task up when they next check in. The fleet circuit breaker still
applies: a push bigger than it allows stops, and says how far it got.

C2 canary rollout (the default for a push to more than one device): one device first, then
10%, then the rest. A wave's tasks are created only when the gate before it opens:
- every task in the current wave has finished and none failed;
- no device in the wave has logged a Critical event since the wave started;
- `WAVE_SOAK` has passed since the last of them finished, so a problem has time to show.

A failure or a Critical event halts the rollout on the spot. Tasks already queued but not yet
picked up are cancelled, and later waves are never created. A person can resume it. The gate
is checked when a wave device reports a result and on its telemetry pushes, so nothing here
needs a scheduler.

Undo is halt-only for installs: SAVIO has no inverse of "install package X". An inverse
exists for USB block/unblock and account disable/enable, which deployments cannot push yet.
"""
from __future__ import annotations

import logging
import math
import uuid
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Device,
    NotificationCategory,
    NotificationSeverity,
    RemediationSource,
    RemediationStatus,
    RemediationTask,
    User,
)
from app.models.base import as_utc, utcnow
from app.models.deployment import Deployment
from app.models.grouping import DeviceGroupMember
from app.models.telemetry import DeviceEventLog
from app.schemas.devices import ONLINE_THRESHOLD
from app.services.audit import AuditService
from app.services.exceptions import ConflictError, NotFoundError, ValidationError
from app.services.notifications import NotificationService
from app.services.remediation.actions import ACTIONS
from app.services.remediation.service import (
    AlreadyQueuedError,
    RemediationError,
    RemediationService,
    RolloutHalted,
)
from app.services.software_catalog import CATALOG

log = logging.getLogger(__name__)

MAX_TARGETS = 1000
SECOND_WAVE_SHARE = 0.10
WAVE_SOAK = timedelta(minutes=10)
_FINISHED = (RemediationStatus.SUCCEEDED, RemediationStatus.FAILED, RemediationStatus.REJECTED)


def plan_waves(devices: list[Device]) -> list[list[Device]]:
    """1 device, then 10% (at least one), then everyone else.

    The canary is an online device when there is one: a first wave that waits for a PC to be
    switched on tells you nothing for hours.
    """
    now = utcnow()

    def online(d: Device) -> bool:
        return d.last_seen_at is not None and now - as_utc(d.last_seen_at) < ONLINE_THRESHOLD

    ordered = sorted(devices, key=lambda d: (not online(d), d.hostname))
    if len(ordered) <= 1:
        return [ordered]
    rest = ordered[1:]
    second = max(1, math.ceil(len(ordered) * SECOND_WAVE_SHARE))
    return [w for w in ([ordered[0]], rest[:second], rest[second:]) if w]


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
        canary: bool = True,
    ) -> tuple[Deployment, dict[str, int], str | None]:
        item = CATALOG.get(package_id)
        if item is None:
            raise ValidationError(f"'{package_id}' is not in the software catalog.")
        devices = await self.resolve_targets(actor.org_id, device_ids, group_ids, exclude_ids)
        if not devices:
            raise ValidationError("No devices selected (after exclusions).")
        if len(devices) > MAX_TARGETS:
            raise ValidationError(f"At most {MAX_TARGETS} devices per push.")

        waves = plan_waves(devices) if canary and len(devices) > 1 else None
        dep = Deployment(
            org_id=actor.org_id, action_id="install_package", params={"package_id": package_id},
            title=f"Install {item.name}", reason=reason, created_by_user_id=actor.id,
            targets={"device_ids": [str(i) for i in device_ids],
                     "group_ids": [str(i) for i in group_ids],
                     "exclude_device_ids": [str(i) for i in exclude_ids]},
        )
        if waves:
            dep.waves = [[str(d.id) for d in w] for w in waves]
            dep.current_wave = 0
            dep.wave_started_at = utcnow()
        self.session.add(dep)
        await self.session.flush()          # dep.id exists only after a flush
        await AuditService(self.session).record(
            org_id=actor.org_id, actor_id=actor.id, action="deployment.create",
            target_type="deployment", target_id=str(dep.id),
            detail={"package": package_id, "devices": len(devices),
                    "waves": [len(w) for w in waves] if waves else None},
        )
        await self.session.commit()

        counts, error = await self._queue(dep, waves[0] if waves else devices, actor)
        counts["waiting"] = sum(len(w) for w in waves[1:]) if waves else 0
        return dep, counts, error

    async def _queue(self, dep: Deployment, devices: list[Device], approver: User):
        svc = RemediationService(self.session)
        counts = {"queued": 0, "already_running": 0, "failed": 0, "not_attempted": 0}
        error = None
        for i, device in enumerate(devices):
            try:
                await svc.create_task(
                    org_id=dep.org_id, device=device, action_id=dep.action_id,
                    params=dep.params, reason=dep.reason,
                    source=RemediationSource.USER, actor_user_id=approver.id, approver=approver,
                    deployment_id=dep.id,
                )
                counts["queued"] += 1
            except AlreadyQueuedError:
                counts["already_running"] += 1
            except RolloutHalted:
                # Halted while this wave was being queued: the rest is not created at all.
                counts["not_attempted"] = len(devices) - i
                break
            except RemediationError as exc:
                counts["failed"] += 1
                error = str(exc)
                if "safety limit" in error.lower():
                    counts["not_attempted"] = len(devices) - i - 1
                    break
        return counts, error

    # ── C2: the gate between waves ─────────────────────────────────────────────────────

    async def advance(self, deployment_id: uuid.UUID) -> None:
        """Release the next wave if the current one is healthy, or halt on a failure."""
        # Two results arriving together must not release the same wave twice.
        dep = await self._locked(deployment_id)
        if dep is None or not dep.waves or dep.halted_at is not None:
            return
        wave_ids = [uuid.UUID(i) for i in dep.waves[dep.current_wave]]
        rows = (await self.session.execute(
            select(RemediationTask, Device.hostname)
            .join(Device, Device.id == RemediationTask.device_id)
            .where(RemediationTask.deployment_id == dep.id,
                   RemediationTask.device_id.in_(wave_ids))
        )).all()

        failed = next((host for t, host in rows if t.status is RemediationStatus.FAILED), None)
        if failed:
            await self.halt(dep, f"It failed on {failed} in wave {dep.current_wave + 1}.")
            return
        critical = (await self.session.execute(
            select(Device.hostname).join(DeviceEventLog, DeviceEventLog.device_id == Device.id)
            .where(DeviceEventLog.device_id.in_(wave_ids), DeviceEventLog.level == "Critical",
                   DeviceEventLog.occurred_at > dep.wave_started_at).limit(1)
        )).scalars().first()
        if critical:
            await self.halt(dep, f"{critical} logged a Critical event after wave "
                                 f"{dep.current_wave + 1} started.")
            return

        if dep.current_wave + 1 >= len(dep.waves):
            return  # the last wave is out; nothing left to gate
        if any(t.status not in _FINISHED for t, _ in rows):
            return
        # A wave whose devices were all already running this install has no tasks of its
        # own; its clock starts when it was released.
        last = max((as_utc(t.completed_at) for t, _ in rows if t.completed_at),
                   default=as_utc(dep.wave_started_at))
        if utcnow() - last < WAVE_SOAK:
            return
        await self._release_next(dep)

    async def _locked(self, deployment_id: uuid.UUID) -> Deployment | None:
        # populate_existing: with expire_on_commit off, a Deployment already in this session
        # would otherwise come back with its old attributes even though the row is locked.
        return (await self.session.execute(
            select(Deployment).where(Deployment.id == deployment_id)
            .with_for_update().execution_options(populate_existing=True)
        )).scalars().first()

    async def _release_next(self, dep: Deployment, approver: User | None = None) -> None:
        """Queue the next wave, approved by `approver` (a person resuming) or else the creator."""
        if approver is None:
            approver = (await self.session.get(User, dep.created_by_user_id)
                        if dep.created_by_user_id else None)
            if approver is None or not approver.is_active:
                # Each wave is approved in the creator's name, so it needs them still here.
                await self.halt(dep, "The person who started this push no longer has an active account.")
                return
        dep.current_wave += 1
        dep.wave_started_at = utcnow()
        await AuditService(self.session).record(
            org_id=dep.org_id, actor_id=approver.id, action="deployment.wave_released",
            target_type="deployment", target_id=str(dep.id),
            detail={"wave": dep.current_wave + 1, "devices": len(dep.waves[dep.current_wave]),
                    "approved_by": approver.email},
        )
        await self.session.commit()
        ids = [uuid.UUID(i) for i in dep.waves[dep.current_wave]]
        devices = list((await self.session.execute(
            select(Device).where(Device.org_id == dep.org_id, Device.id.in_(ids),
                                 Device.is_active.is_(True))
        )).scalars())
        # create_task re-checks the approver's authority for every device: a creator demoted
        # since the push started cannot approve the next wave.
        try:
            _, error = await self._queue(dep, devices, approver)
        except Exception:
            # Not a refusal but a crash, part-way through the wave. Halt so it is visible
            # rather than leaving the rest of the wave silently never created.
            await self.session.rollback()
            dep = await self._locked(dep.id)
            if dep is not None and dep.halted_at is None:
                await self.halt(dep, f"Wave {dep.current_wave + 1} stopped part-way: an internal error.")
            raise
        if error:
            await self.halt(dep, f"Wave {dep.current_wave + 1} could not be queued: {error}"[:300])

    async def halt(self, dep: Deployment, reason: str, *, actor: User | None = None) -> None:
        """Stop the rollout: no further waves, and nothing queued-but-not-started runs."""
        dep.halted_at = utcnow()
        dep.halt_reason = reason[:300]
        # One conditional statement, not read-then-write: a task an agent claims at the same
        # moment is either cancelled here or dispatched there, never both (the claim is
        # conditional too). Tasks waiting for approval are cancelled as well, so nobody can
        # approve one of a halted rollout from the queue.
        cancelled = (await self.session.execute(
            update(RemediationTask)
            .where(RemediationTask.deployment_id == dep.id,
                   RemediationTask.status.in_((RemediationStatus.APPROVED,
                                               RemediationStatus.PENDING_APPROVAL)))
            .values(status=RemediationStatus.REJECTED,
                    result={"output": "Not run: the rollout was halted."}, completed_at=utcnow())
            .execution_options(synchronize_session=False)
        )).rowcount
        await AuditService(self.session).record(
            org_id=dep.org_id, actor_id=actor.id if actor else None, action="deployment.halt",
            target_type="deployment", target_id=str(dep.id),
            detail={"reason": dep.halt_reason, "wave": (dep.current_wave or 0) + 1,
                    "cancelled": cancelled, "automatic": actor is None},
        )
        await NotificationService(self.session).notify(
            org_id=dep.org_id, category=NotificationCategory.REMEDIATION,
            severity=NotificationSeverity.CRITICAL if actor is None else NotificationSeverity.WARNING,
            title="Rollout halted", message=f"{dep.title}: {dep.halt_reason}", link="/software",
        )
        await self.session.commit()

    async def halt_by(self, *, actor: User, deployment_id: uuid.UUID, reason: str) -> Deployment:
        await self._own(actor, deployment_id)
        dep = await self._locked(deployment_id)   # waits for any create_task holding it
        if dep.halted_at is not None:
            raise ConflictError("This rollout is already halted.")
        await self.halt(dep, f"Halted by {actor.email}: {reason}", actor=actor)
        return dep

    async def resume(self, *, actor: User, deployment_id: uuid.UUID) -> Deployment:
        """A person looked at the halt and says go on: release the next wave now.

        Tasks cancelled by the halt are not re-queued; their devices can be pushed again.
        """
        await self._own(actor, deployment_id)
        dep = await self._locked(deployment_id)
        if dep.halted_at is None:
            raise ConflictError("This rollout is not halted.")
        # The next wave is approved in the resumer's name, so they need the authority to
        # approve this action themselves: a technician cannot resume an install the org says
        # only an admin may approve, by borrowing the admin creator's authority.
        await RemediationService(self.session)._assert_may_approve(actor, ACTIONS[dep.action_id].tier)
        await AuditService(self.session).record(
            org_id=dep.org_id, actor_id=actor.id, action="deployment.resume",
            target_type="deployment", target_id=str(dep.id),
            detail={"halt_reason": dep.halt_reason, "wave": (dep.current_wave or 0) + 1},
        )
        dep.halted_at = None
        dep.halt_reason = None
        await self.session.commit()
        if dep.waves and dep.current_wave + 1 < len(dep.waves):
            await self._release_next(dep, approver=actor)
        return dep

    async def advance_for_device(self, device_id: uuid.UUID) -> None:
        """On a telemetry push: re-check the gate of any live rollout this device is in."""
        dep_ids = (await self.session.execute(
            select(RemediationTask.deployment_id).distinct()
            .join(Deployment, Deployment.id == RemediationTask.deployment_id)
            .where(RemediationTask.device_id == device_id,
                   Deployment.waves.is_not(None), Deployment.halted_at.is_(None),
                   Deployment.created_at >= utcnow() - timedelta(days=14))
        )).scalars().all()
        for dep_id in dep_ids:
            await self.advance(dep_id)

    async def _own(self, actor: User, deployment_id: uuid.UUID) -> Deployment:
        dep = await self.session.get(Deployment, deployment_id)
        if dep is None or dep.org_id != actor.org_id:
            raise NotFoundError("Deployment not found")
        return dep

    # ── Reading ───────────────────────────────────────────────────────────────────────

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
        dep = await self._own(actor, deployment_id)
        rows = (await self.session.execute(
            select(RemediationTask, Device.hostname)
            .join(Device, Device.id == RemediationTask.device_id)
            .where(RemediationTask.deployment_id == dep.id)
            .order_by(Device.hostname)
        )).all()
        return dep, rows
