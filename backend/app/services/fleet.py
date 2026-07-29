"""Fleet-wide correlation + mass remediation.

Rolls the per-device compliance evaluation and pending Windows updates up into a ranked
list of issues — each carrying every affected device and, where a safe remediation exists,
the action that fixes it on all of them. Mass remediation just fans the existing
create+approve path out over a set of devices (tiers still enforced per device).
"""
import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Device,
    DeviceWindowsUpdate,
    RemediationSource,
    RemediationStatus,
    User,
)
from app.repositories.devices import DeviceRepository
from app.schemas.fleet import BulkRemediateResult, FleetAffected, FleetIssue
from app.services.compliance import ComplianceService
from app.services.remediation.service import RemediationError, RemediationService

# Compliance checks surfaced as fleet issues (patch is covered by the per-KB breakdown).
# key -> (title, severity, fix_action_id)
_CHECK_ISSUES: dict[str, tuple[str, str, str | None]] = {
    "disk": ("Low disk space", "medium", "clear_system_temp"),
    "defender": ("Microsoft Defender not running", "high", None),
    "firewall": ("Windows Firewall not running", "high", None),
    "no_critical_events": ("Critical system errors", "high", None),
    "no_banned_software": ("Restricted software installed", "high", None),
    "agent_reporting": ("Agent not reporting", "low", None),
}


class FleetService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def issues(self, *, org_id: uuid.UUID) -> list[FleetIssue]:
        issues: list[FleetIssue] = []

        # 1. Compliance-check failures, grouped across devices.
        compliance = await ComplianceService(self.session).list_devices(org_id=org_id)
        by_check: dict[str, list[tuple[uuid.UUID, str, str]]] = defaultdict(list)
        for d in compliance:
            for c in d.checks:
                if c.key in _CHECK_ISSUES and c.status == "fail":
                    by_check[c.key].append((d.device_id, d.hostname, c.detail))
        for key, (title, severity, fix) in _CHECK_ISSUES.items():
            devs = by_check.get(key)
            if not devs:
                continue
            # A representative detail (most common), just for context.
            detail = devs[0][2] if len({x[2] for x in devs}) == 1 else f"{len(devs)} devices"
            issues.append(FleetIssue(
                key=key, category="compliance", title=title, detail=detail, severity=severity,
                fix_action_id=fix, fix_params=None,
                affected=[FleetAffected(device_id=x[0], hostname=x[1]) for x in devs],
            ))

        # 2. Pending Windows updates, grouped by KB.
        rows = (await self.session.execute(
            select(
                DeviceWindowsUpdate.kb_article_id, DeviceWindowsUpdate.title,
                Device.id, Device.hostname,
            )
            .join(Device, Device.id == DeviceWindowsUpdate.device_id)
            .where(DeviceWindowsUpdate.org_id == org_id, DeviceWindowsUpdate.is_installed.is_(False))
        )).all()
        by_kb: dict[str, dict] = defaultdict(lambda: {"title": "", "devs": []})
        for kb, title, dev_id, hostname in rows:
            by_kb[kb]["title"] = title
            by_kb[kb]["devs"].append((dev_id, hostname))
        for kb, info in by_kb.items():
            issues.append(FleetIssue(
                key=f"update:{kb}", category="update",
                title=f"{kb} pending", detail=info["title"], severity="medium",
                fix_action_id="windows_update_install", fix_params={"kb_article_id": kb},
                affected=[FleetAffected(device_id=d[0], hostname=d[1]) for d in info["devs"]],
            ))

        issues.sort(key=lambda i: len(i.affected), reverse=True)
        return issues

    async def bulk_remediate(
        self, *, actor: User, device_ids: list[uuid.UUID], action_id: str,
        params: dict[str, str] | None, reason: str,
    ) -> BulkRemediateResult:
        """Push one remediation to every listed device. Each goes through the normal
        create+approve path, so tiers and the org's fleet circuit-breaker still apply."""
        repo = DeviceRepository(self.session)
        svc = RemediationService(self.session)
        queued = failed = 0
        error: str | None = None
        for did in device_ids:
            device = await repo.get(did)
            if device is None or device.org_id != actor.org_id:
                failed += 1
                continue
            try:
                task = await svc.create_task(
                    org_id=actor.org_id, device=device, action_id=action_id,
                    params=params, reason=reason, source=RemediationSource.USER,
                    actor_user_id=actor.id,
                )
                if task.status is RemediationStatus.PENDING_APPROVAL:
                    await svc.approve_task(actor=actor, task_id=task.id)
                queued += 1
            except RemediationError as exc:
                failed += 1
                error = str(exc)
                # The fleet safety limit stops the whole batch — report and bail out.
                if "safety limit" in str(exc).lower():
                    break
            except Exception as exc:  # unknown action, param error, etc.
                failed += 1
                error = str(exc)
        return BulkRemediateResult(queued=queued, failed=failed, error=error)
