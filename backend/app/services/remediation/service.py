import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import (
    Device,
    NotificationCategory,
    NotificationSeverity,
    RemediationSource,
    RemediationStatus,
    RemediationTask,
    User,
    UserRole,
)
from app.models.base import utcnow
from app.repositories.devices import DeviceRepository

settings = get_settings()
from app.repositories.remediation import RemediationRepository
from app.services.audit import AuditService
from app.services.exceptions import ConflictError, NotFoundError, ServiceError
from app.services.notifications import NotificationService
from app.services.settings import SettingsService
from app.services.remediation.actions import (
    ACTIONS,
    SAFE_APP_PROCESSES,
    SAFE_SERVICES,
    RemediationTier,
    get_action,
)


class RemediationError(ServiceError):
    pass


# Which roles may approve a task of a given tier. AUTOMATIC never reaches approval.
_APPROVER_ROLES: dict[RemediationTier, set[UserRole]] = {
    RemediationTier.APPROVAL_REQUIRED: {UserRole.ADMIN, UserRole.TECHNICIAN},
    RemediationTier.ADMIN_ONLY: {UserRole.ADMIN},
}


class RemediationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = RemediationRepository(session)
        self.devices = DeviceRepository(session)
        self.audit = AuditService(session)
        self.notifications = NotificationService(session)
        self.settings = SettingsService(session)

    # -- Creation --------------------------------------------------------------

    async def create_task(
        self,
        *,
        org_id: uuid.UUID,
        device: Device,
        action_id: str,
        params: dict[str, Any] | None,
        reason: str,
        source: RemediationSource,
        actor_user_id: uuid.UUID | None,
    ) -> RemediationTask:
        action = get_action(action_id)
        if action is None:
            raise RemediationError(f"Unknown remediation action '{action_id}'.")
        params = self._validate_params(action_id, params)

        # Blast-radius / fleet circuit breaker: count recent remediations for the org.
        window_start = utcnow() - timedelta(seconds=settings.remediation_burst_window_seconds)
        recent = await self.repo.count_recent_for_org(org_id, window_start)
        if recent >= settings.remediation_hard_burst:
            raise RemediationError(
                "Fleet safety limit reached: too many remediations were requested in a short "
                "window. New actions are paused — please review activity and try again shortly."
            )
        breaker_tripped = recent >= settings.remediation_auto_approve_burst

        # Tier drives the initial status: automatic is pre-approved; everything else
        # waits for a human. This is enforced here in the service, never by the client.
        # The org-level automation kill-switch — and the circuit breaker above — can
        # force even automatic actions to wait for a human.
        org_settings = await self.settings.ensure(org_id)
        auto_ok = (
            action.tier is RemediationTier.AUTOMATIC
            and org_settings.auto_approve_automatic
            and not breaker_tripped
        )
        status = RemediationStatus.APPROVED if auto_ok else RemediationStatus.PENDING_APPROVAL

        task = await self.repo.add(
            RemediationTask(
                org_id=org_id,
                device_id=device.id,
                action_id=action_id,
                params=params or None,
                tier=action.tier.value,
                status=status,
                reason=reason,
                source=source,
                requested_by_user_id=actor_user_id,
            )
        )
        await self.audit.record(
            org_id=org_id,
            actor_id=actor_user_id,
            action="remediation.create",
            target_type="remediation_task",
            target_id=str(task.id),
            detail={"action": action_id, "tier": action.tier.value, "status": status.value,
                    "device": device.hostname, "source": source.value},
        )
        if status is RemediationStatus.PENDING_APPROVAL:
            approver = "an admin" if action.tier is RemediationTier.ADMIN_ONLY else "a technician or admin"
            await self.notifications.notify(
                org_id=org_id,
                category=NotificationCategory.REMEDIATION,
                severity=NotificationSeverity.WARNING,
                title="Approval needed",
                message=f"{action.label} on {device.hostname} needs approval from {approver}.",
                link="/self-healing",
            )
        await self.session.commit()
        return task

    def _validate_params(
        self, action_id: str, params: dict[str, Any] | None
    ) -> dict[str, Any]:
        action = ACTIONS[action_id]
        params = params or {}
        # Only the parameters the action declares are accepted.
        extra = set(params) - set(action.params)
        if extra:
            raise RemediationError(f"Unexpected parameter(s) for {action_id}: {sorted(extra)}")
        if "service_name" in action.params:
            name = params.get("service_name")
            if name not in SAFE_SERVICES:
                raise RemediationError(
                    f"Service '{name}' is not on the allowlist of restartable services."
                )
        if "process_name" in action.params:
            name = params.get("process_name") or ""
            # Case-insensitive allowlist check — the agent will match the process the same way.
            if name.lower() not in {p.lower() for p in SAFE_APP_PROCESSES}:
                raise RemediationError(
                    f"Application '{name}' is not on the allowlist of restartable applications."
                )
        return params

    # -- Approval workflow (portal staff) --------------------------------------

    async def approve_task(self, *, actor: User, task_id: uuid.UUID) -> RemediationTask:
        task = await self._get_owned(actor.org_id, task_id)
        if task.status is not RemediationStatus.PENDING_APPROVAL:
            raise ConflictError("Only a pending task can be approved.")

        tier = RemediationTier(task.tier)
        allowed = _APPROVER_ROLES.get(tier, set())
        # Org policy can tighten the standard tier to admin-only approval.
        if tier is RemediationTier.APPROVAL_REQUIRED:
            org_settings = await self.settings.ensure(actor.org_id)
            if org_settings.require_admin_for_approval_tier:
                allowed = {UserRole.ADMIN}
        if actor.role not in allowed:
            # A technician cannot approve an admin-only action; a user cannot approve anything.
            raise RemediationError("Your role cannot approve a task at this trust tier.")

        task.status = RemediationStatus.APPROVED
        task.approved_by_user_id = actor.id
        await self.audit.record(
            org_id=actor.org_id,
            actor_id=actor.id,
            action="remediation.approve",
            target_type="remediation_task",
            target_id=str(task.id),
            detail={"action": task.action_id, "tier": task.tier},
        )
        await self.session.commit()
        return task

    async def reject_task(self, *, actor: User, task_id: uuid.UUID) -> RemediationTask:
        task = await self._get_owned(actor.org_id, task_id)
        if task.status is not RemediationStatus.PENDING_APPROVAL:
            raise ConflictError("Only a pending task can be rejected.")
        task.status = RemediationStatus.REJECTED
        task.approved_by_user_id = actor.id
        await self.audit.record(
            org_id=actor.org_id,
            actor_id=actor.id,
            action="remediation.reject",
            target_type="remediation_task",
            target_id=str(task.id),
        )
        await self.session.commit()
        return task

    async def list_for_org(self, *, actor: User) -> list[RemediationTask]:
        return await self.repo.list_by_org(actor.org_id)

    # -- Agent-facing (device executes approved work) --------------------------

    async def claim_for_device(self, *, device: Device) -> list[RemediationTask]:
        """Return approved tasks for this device and mark them dispatched."""
        tasks = await self.repo.list_approved_for_device(device.id)
        for task in tasks:
            task.status = RemediationStatus.DISPATCHED
        await self.session.commit()
        return tasks

    async def record_result(
        self, *, device: Device, task_id: uuid.UUID, success: bool, output: str
    ) -> RemediationTask:
        task = await self.repo.get(task_id)
        if task is None or task.device_id != device.id:
            raise NotFoundError("Remediation task not found")
        if task.status is not RemediationStatus.DISPATCHED:
            raise ConflictError("Task is not awaiting a result.")
        task.status = RemediationStatus.SUCCEEDED if success else RemediationStatus.FAILED
        task.result = {"output": output[:4000]}
        task.completed_at = utcnow()
        await self.audit.record(
            org_id=device.org_id,
            actor_id=None,
            action="remediation.result",
            target_type="remediation_task",
            target_id=str(task.id),
            detail={"action": task.action_id, "success": success},
        )
        if not success:
            action = get_action(task.action_id)
            label = action.label if action else task.action_id
            await self.notifications.notify(
                org_id=device.org_id,
                category=NotificationCategory.REMEDIATION,
                severity=NotificationSeverity.CRITICAL,
                title="Remediation failed",
                message=f"{label} failed on {device.hostname}.",
                link="/self-healing",
            )
        await self.session.commit()
        return task

    async def _get_owned(self, org_id: uuid.UUID, task_id: uuid.UUID) -> RemediationTask:
        task = await self.repo.get(task_id)
        if task is None or task.org_id != org_id:
            raise NotFoundError("Remediation task not found")
        return task
