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
    User,
)
from app.models.telemetry import (
    UPDATE_FAILED,
    UPDATE_PENDING,
    UPDATE_PENDING_RESTART,
)
from app.repositories.devices import DeviceRepository
from app.schemas.fleet import BulkRemediateResult, FleetAffected, FleetIssue
from app.services.compliance import ComplianceService
from app.services.remediation.service import (
    AlreadyQueuedError,
    RemediationError,
    RemediationService,
)

# Compliance checks surfaced as fleet issues (patch is covered by the per-KB breakdown).
# key -> (title, severity, fix_action_id, note_when_no_fix)
#
# Every entry without a fix carries a reason. Most fleet issues genuinely cannot be pushed —
# the device is offline, or the remedy depends on what specifically failed — and a page that
# just omits the button for those looks broken rather than honest.
_CHECK_ISSUES: dict[str, tuple[str, str, str | None, str | None]] = {
    "disk": ("Low disk space", "medium", "clear_system_temp", None),
    "defender": (
        "Microsoft Defender not running", "high", None,
        "Starting a security service needs the elevated agent, which doesn't expose that "
        "action yet. Start WinDefend on the device, or push it through Intune/GPO.",
    ),
    "firewall": (
        "Windows Firewall not running", "high", None,
        "Starting a security service needs the elevated agent, which doesn't expose that "
        "action yet. Start MpsSvc on the device, or push it through Intune/GPO.",
    ),
    "no_critical_events": (
        "Critical system errors", "high", None,
        "There's no single fix — the right action depends on what's failing. Open a device "
        "to see its errors; the Health tab suggests a fix per error source.",
    ),
    "no_banned_software": (
        "Restricted software installed", "high", None,
        "Detection only for now — removal isn't automated. Uninstall on the device, or "
        "block it centrally.",
    ),
    "agent_reporting": (
        "Agent not reporting", "low", None,
        "Nothing can be pushed to a device that isn't checking in. Confirm it's powered on "
        "and reaching the backend — a quarantined agent is the usual cause.",
    ),
}


class FleetService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def issues(
        self, *, org_id: uuid.UUID, compliance: list | None = None
    ) -> list[FleetIssue]:
        """`compliance` lets a caller that has already scored the fleet hand the scores in.
        The dashboard needs both these issues and the fleet summary; without this it would
        score every device twice to render one page."""
        issues: list[FleetIssue] = []

        # 1. Compliance-check failures, grouped across devices.
        if compliance is None:
            compliance = await ComplianceService(self.session).list_devices(org_id=org_id)
        by_check: dict[str, list[tuple[uuid.UUID, str, str]]] = defaultdict(list)
        for d in compliance:
            for c in d.checks:
                if c.key in _CHECK_ISSUES and c.status == "fail":
                    by_check[c.key].append((d.device_id, d.hostname, c.detail))
        for key, (title, severity, fix, note) in _CHECK_ISSUES.items():
            devs = by_check.get(key)
            if not devs:
                continue
            # A representative detail (most common), just for context.
            detail = devs[0][2] if len({x[2] for x in devs}) == 1 else f"{len(devs)} devices"
            issues.append(FleetIssue(
                key=key, category="compliance", title=title, detail=detail, severity=severity,
                fix_action_id=fix, fix_params=None, fix_note=None if fix else note,
                affected=[FleetAffected(device_id=x[0], hostname=x[1]) for x in devs],
            ))

        # 2. Windows updates not yet in effect, grouped by KB AND by why. Pushing an install
        # is only the answer for one of these: an update that is installed and waiting on a
        # reboot would be reinstalled to no effect, which is what happened before the state
        # existed — every one of them read as "pending".
        rows = (await self.session.execute(
            select(
                DeviceWindowsUpdate.kb_article_id, DeviceWindowsUpdate.title,
                DeviceWindowsUpdate.state, DeviceWindowsUpdate.error_code,
                Device.id, Device.hostname,
            )
            .join(Device, Device.id == DeviceWindowsUpdate.device_id)
            .where(DeviceWindowsUpdate.org_id == org_id,
                   DeviceWindowsUpdate.state.in_(
                       (UPDATE_PENDING, UPDATE_PENDING_RESTART, UPDATE_FAILED)))
        )).all()
        by_kb: dict[tuple[str, str], dict] = defaultdict(
            lambda: {"title": "", "code": None, "devs": []}
        )
        for kb, title, state, code, dev_id, hostname in rows:
            group = by_kb[(state, kb)]
            group["title"] = title
            group["code"] = group["code"] or code
            group["devs"].append((dev_id, hostname))

        for (state, kb), info in by_kb.items():
            if state == UPDATE_PENDING_RESTART:
                title, severity, fix, note = (
                    f"{kb} installed — restart pending", "medium", None,
                    "The update is already on these devices; only a reboot applies it. "
                    "Reinstalling changes nothing. ASTRA never reboots a machine on its own, "
                    "so ask the user to restart, or schedule one through Intune/GPO.",
                )
            elif state == UPDATE_FAILED:
                code = info["code"]
                # Retrying is what Windows itself offers, so the button stays — but the code
                # is shown, because a repeatedly failing download needs a cause, not a retry.
                title, severity, fix, note = (
                    f"{kb} failed to install{f' ({code})' if code else ''}", "high",
                    "windows_update_install", None,
                )
            else:
                title, severity, fix, note = f"{kb} pending", "medium", "windows_update_install", None

            issues.append(FleetIssue(
                key=f"update:{state}:{kb}", category="update",
                title=title, detail=info["title"], severity=severity,
                fix_action_id=fix,
                fix_params={"kb_article_id": kb} if fix else None,
                fix_note=note,
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
        queued = failed = already_running = 0
        error: str | None = None
        for did in device_ids:
            device = await repo.get(did)
            if device is None or device.org_id != actor.org_id:
                failed += 1
                continue
            try:
                # Approve inline: the operator picked this action and pressed Fix all, so
                # creating then approving would raise an "Approval needed" notification per
                # device for something cleared milliseconds later — and leave every task
                # stranded as pending if the approve half were refused.
                await svc.create_task(
                    org_id=actor.org_id, device=device, action_id=action_id,
                    params=params, reason=reason, source=RemediationSource.USER,
                    actor_user_id=actor.id, approver=actor,
                )
                queued += 1
            except AlreadyQueuedError:
                # Not a failure: this device is already doing the thing being asked for.
                # Counting it as failed would read as "the push didn't work" and invite the
                # operator to press Fix all again, which is exactly how duplicates pile up.
                already_running += 1
            except RemediationError as exc:
                failed += 1
                error = str(exc)
                # The fleet safety limit stops the whole batch — report and bail out.
                if "safety limit" in str(exc).lower():
                    break
            except Exception as exc:  # unknown action, param error, etc.
                failed += 1
                error = str(exc)
        return BulkRemediateResult(
            queued=queued, failed=failed, already_running=already_running, error=error
        )
