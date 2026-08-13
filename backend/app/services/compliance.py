"""Compliance / security posture evaluation.

Read-only over data ASTRA already collects (Windows updates, disk telemetry, services,
event logs, installed apps, heartbeat) plus the org's banned-software list. Nothing here
changes device state — it scores devices against a fixed set of checks so the portal can
show a fleet posture and, where a safe remediation exists, offer a one-click fix.
"""
import uuid
from datetime import timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    BannedSoftware,
    Device,
    DeviceEventLog,
    DeviceInstalledApp,
    DeviceService,
    DeviceWindowsUpdate,
    TelemetrySnapshot,
    User,
)
from app.models.telemetry import (
    UPDATE_FAILED,
    UPDATE_PENDING,
    UPDATE_PENDING_RESTART,
)
from app.models.base import as_utc, utcnow
from app.schemas.compliance import (
    CheckBreakdown,
    CheckResult,
    ComplianceSummary,
    DeviceCompliance,
    UsbPosture,
)
from app.services.audit import AuditService
from app.services.exceptions import ConflictError, NotFoundError, ValidationError

# The checks and the remediation (if any) that fixes each. Order = display order.
CHECKS: list[tuple[str, str, str | None]] = [
    ("patch", "Windows updates installed", "windows_update_install"),
    ("disk", "Enough free disk space", "clear_system_temp"),
    ("defender", "Microsoft Defender running", None),
    ("firewall", "Windows Firewall running", None),
    ("no_critical_events", "No critical system errors", None),
    ("agent_reporting", "Agent reporting in", None),
    ("no_banned_software", "No restricted software", None),
]
CHECK_LABELS = {key: label for key, label, _ in CHECKS}
CHECK_FIX = {key: fix for key, _, fix in CHECKS}

DISK_FREE_MIN_PCT = 10.0
STALE_AFTER = timedelta(hours=24)

#: Shortest restricted-software pattern we will accept. Substring matching means "e" fails
#: nearly every device in the fleet, and the admin who typed it has no way to see why.
MIN_PATTERN_LENGTH = 3


def _like_literal(value: str) -> str:
    """Escape the LIKE metacharacters so a pattern matches the name and nothing else.

    Real product names contain "_" — TeamViewer_Host, Zoom_Installer — and "_" is also
    LIKE's single-character wildcard, so an admin pasting an exact name gets a pattern that
    quietly matches more than they typed. A stray "%" is worse: it matches every installed
    app, and the whole fleet fails the restricted-software check at once.
    """
    return value.replace("\\", r"\\").replace("%", r"\%").replace("_", r"\_")


class ComplianceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    # ── Banned software list ──────────────────────────────────────────────────

    async def list_banned(self, *, org_id: uuid.UUID) -> list[BannedSoftware]:
        result = await self.session.execute(
            select(BannedSoftware).where(BannedSoftware.org_id == org_id).order_by(BannedSoftware.name)
        )
        return list(result.scalars().all())

    async def add_banned(self, *, actor: User, name: str) -> BannedSoftware:
        name = name.strip()
        pattern = name.lower()
        if len(pattern) < MIN_PATTERN_LENGTH:
            raise ValidationError(
                f"Enter at least {MIN_PATTERN_LENGTH} characters — a shorter name matches "
                "part of almost every application and would fail your whole fleet."
            )
        exists = await self.session.execute(
            select(BannedSoftware).where(
                BannedSoftware.org_id == actor.org_id, BannedSoftware.pattern == pattern
            )
        )
        if exists.scalar_one_or_none() is not None:
            raise ConflictError("That software is already on the list")
        row = BannedSoftware(org_id=actor.org_id, name=name, pattern=pattern)
        self.session.add(row)
        await self.session.flush()
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="compliance.banned_add",
            target_type="banned_software", target_id=str(row.id), detail={"name": name},
        )
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def remove_banned(self, *, actor: User, banned_id: uuid.UUID) -> None:
        row = await self.session.get(BannedSoftware, banned_id)
        if row is None or row.org_id != actor.org_id:
            raise NotFoundError("Not found")
        name = row.name
        await self.session.delete(row)
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="compliance.banned_remove",
            target_type="banned_software", target_id=str(banned_id), detail={"name": name},
        )
        await self.session.commit()

    # ── Evaluation ────────────────────────────────────────────────────────────

    async def _evaluate(
        self, *, org_id: uuid.UUID, offset: int | None = None, limit: int | None = None
    ) -> tuple[list[DeviceCompliance], int]:
        """Score the org's devices. With offset/limit only that slice is scored — the fleet
        summary still needs every device, but the per-device table does not, and evaluating
        two thousand of them to render fifty is the whole reason this page was slow.

        Returns (rows, total_devices_in_org).
        """
        base = select(Device).where(Device.org_id == org_id).order_by(Device.hostname)
        total = int(await self.session.scalar(
            select(func.count()).select_from(base.order_by(None).subquery())
        ) or 0)
        stmt = base
        if offset is not None and limit is not None:
            stmt = stmt.offset(offset).limit(limit)
        devices = list((await self.session.execute(stmt)).scalars().all())
        if not devices:
            return [], total

        # Updates still to install, split by why. These are not the same finding: a device
        # that installed its updates and needs a reboot is nearly patched and the fix is a
        # restart, while one whose download keeps failing needs someone to look at why. Both
        # used to read as "N update(s) pending", so both got a pointless reinstall pushed.
        pending: dict[uuid.UUID, int] = dict((await self.session.execute(
            select(DeviceWindowsUpdate.device_id, func.count())
            .where(DeviceWindowsUpdate.org_id == org_id,
                   DeviceWindowsUpdate.state == UPDATE_PENDING)
            .group_by(DeviceWindowsUpdate.device_id)
        )).all())
        awaiting_restart: dict[uuid.UUID, int] = dict((await self.session.execute(
            select(DeviceWindowsUpdate.device_id, func.count())
            .where(DeviceWindowsUpdate.org_id == org_id,
                   DeviceWindowsUpdate.state == UPDATE_PENDING_RESTART)
            .group_by(DeviceWindowsUpdate.device_id)
        )).all())
        failed_updates: dict[uuid.UUID, list[tuple[str, str | None]]] = {}
        for dev_id, kb, code in (await self.session.execute(
            select(DeviceWindowsUpdate.device_id, DeviceWindowsUpdate.kb_article_id,
                   DeviceWindowsUpdate.error_code)
            .where(DeviceWindowsUpdate.org_id == org_id,
                   DeviceWindowsUpdate.state == UPDATE_FAILED)
        )).all():
            failed_updates.setdefault(dev_id, []).append((kb, code))
        have_updates = {r[0] for r in (await self.session.execute(
            select(DeviceWindowsUpdate.device_id).where(DeviceWindowsUpdate.org_id == org_id).distinct()
        )).all()}

        # Critical events per device (the collector already keeps only the last 24h).
        critical: dict[uuid.UUID, int] = dict((await self.session.execute(
            select(DeviceEventLog.device_id, func.count())
            .where(DeviceEventLog.org_id == org_id, DeviceEventLog.level == "Critical")
            .group_by(DeviceEventLog.device_id)
        )).all())

        # Latest telemetry snapshot per device (for disk free %).
        sub = (select(TelemetrySnapshot.device_id, func.max(TelemetrySnapshot.collected_at).label("mx"))
               .where(TelemetrySnapshot.org_id == org_id)
               .group_by(TelemetrySnapshot.device_id).subquery())
        latest = {s.device_id: s for s in (await self.session.execute(
            select(TelemetrySnapshot).join(sub, and_(
                TelemetrySnapshot.device_id == sub.c.device_id,
                TelemetrySnapshot.collected_at == sub.c.mx))
        )).scalars().all()}

        # Security-relevant services (current status). name is stored as the service key.
        svc_rows = (await self.session.execute(
            select(DeviceService.device_id, func.lower(DeviceService.name), DeviceService.status)
            .where(DeviceService.org_id == org_id,
                   func.lower(DeviceService.name).in_(["windefend", "mpssvc"]))
        )).all()
        services: dict[uuid.UUID, dict[str, str]] = {}
        for dev_id, sname, sstatus in svc_rows:
            services.setdefault(dev_id, {})[sname] = sstatus
        have_services = {r[0] for r in (await self.session.execute(
            select(DeviceService.device_id).where(DeviceService.org_id == org_id).distinct()
        )).all()}

        # Banned software: which devices have a matching installed app.
        banned = await self.list_banned(org_id=org_id)
        banned_hits: dict[uuid.UUID, list[str]] = {}
        have_apps: set[uuid.UUID] = set()
        if banned:
            conds = [
                func.lower(DeviceInstalledApp.name).like(
                    f"%{_like_literal(b.pattern)}%", escape="\\"
                )
                for b in banned
            ]
            hit_rows = (await self.session.execute(
                select(DeviceInstalledApp.device_id, DeviceInstalledApp.name)
                .where(DeviceInstalledApp.org_id == org_id, or_(*conds))
            )).all()
            for dev_id, app_name in hit_rows:
                banned_hits.setdefault(dev_id, []).append(app_name)
            have_apps = {r[0] for r in (await self.session.execute(
                select(DeviceInstalledApp.device_id).where(DeviceInstalledApp.org_id == org_id).distinct()
            )).all()}

        now = utcnow()
        results: list[DeviceCompliance] = []
        for d in devices:
            checks: list[CheckResult] = []

            # patch — the detail names the actual blocker, because the three cases need
            # three different responses and only one of them is "push the update again".
            if d.id not in have_updates:
                checks.append(self._chk("patch", "unknown", "No update scan yet"))
            else:
                n = pending.get(d.id, 0)
                restart_n = awaiting_restart.get(d.id, 0)
                failures = failed_updates.get(d.id, [])
                if failures:
                    kb, code = failures[0]
                    extra = f" ({code})" if code else ""
                    more = f" +{len(failures) - 1} more" if len(failures) > 1 else ""
                    detail = f"{kb} failed{extra}{more}"
                elif n:
                    detail = f"{n} update(s) pending"
                elif restart_n:
                    detail = f"{restart_n} installed — restart to finish"
                else:
                    detail = "Up to date"
                ok = not failures and n == 0 and restart_n == 0
                checks.append(self._chk("patch", "pass" if ok else "fail", detail))

            # disk
            snap = latest.get(d.id)
            if snap is None:
                checks.append(self._chk("disk", "unknown", "No telemetry yet"))
            else:
                free = _min_free_pct(snap.disks)
                if free is None:
                    checks.append(self._chk("disk", "unknown", "No disk data"))
                else:
                    checks.append(self._chk("disk", "pass" if free >= DISK_FREE_MIN_PCT else "fail",
                                            f"{free:.0f}% free"))

            # defender / firewall (from current service status)
            checks.append(self._svc_check("defender", "windefend", d.id, services, have_services))
            checks.append(self._svc_check("firewall", "mpssvc", d.id, services, have_services))

            # critical events (absence = healthy)
            c = critical.get(d.id, 0)
            checks.append(self._chk("no_critical_events", "pass" if c == 0 else "fail",
                                    "None" if c == 0 else f"{c} critical event(s) (24h)"))

            # agent reporting
            fresh = d.last_seen_at is not None and now - as_utc(d.last_seen_at) < STALE_AFTER
            checks.append(self._chk("agent_reporting", "pass" if fresh else "fail",
                                    "Reporting" if fresh else "Not reporting (offline > 24h)"))

            # banned software (only when a list exists)
            if banned:
                hits = banned_hits.get(d.id)
                if hits:
                    checks.append(self._chk("no_banned_software", "fail", ", ".join(sorted(set(hits))[:5])))
                elif d.id in have_apps:
                    checks.append(self._chk("no_banned_software", "pass", "None found"))
                else:
                    checks.append(self._chk("no_banned_software", "unknown", "No app inventory yet"))

            passed = sum(1 for c in checks if c.status == "pass")
            failed = sum(1 for c in checks if c.status == "fail")
            known = passed + failed
            score = round(passed / known * 100) if known else 0
            if known == 0:
                dstatus = "unknown"
            elif failed == 0:
                dstatus = "compliant"
            elif failed == 1:
                dstatus = "at_risk"
            else:
                dstatus = "non_compliant"

            results.append(DeviceCompliance(
                device_id=d.id, hostname=d.hostname, status=dstatus,
                score=score, passed=passed, failed=failed, checks=checks,
                usb_storage_blocked=d.usb_storage_blocked,
            ))
        return results, total

    async def list_devices(self, *, org_id: uuid.UUID) -> list[DeviceCompliance]:
        rows, _ = await self._evaluate(org_id=org_id)
        return rows

    async def list_devices_page(
        self,
        *,
        org_id: uuid.UUID,
        needs_attention: bool = False,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[DeviceCompliance], int]:
        """One page of scored devices.

        `needs_attention` is applied here rather than in SQL because a device's status is
        computed from telemetry, updates, services and events — there is no column to filter
        on. So that view scores the fleet and pages the result: the response stays small,
        which is the point, even though the work behind it does not shrink.

        The plain list does page in the database, which is the common case.
        """
        if not needs_attention:
            return await self._evaluate(org_id=org_id, offset=offset, limit=limit)

        rows, _ = await self._evaluate(org_id=org_id)
        rows = [r for r in rows if r.status in ("non_compliant", "at_risk")]
        rows.sort(key=lambda r: r.score)
        return rows[offset : offset + limit], len(rows)

    async def get_device(self, *, org_id: uuid.UUID, device_id: uuid.UUID) -> DeviceCompliance:
        rows, _ = await self._evaluate(org_id=org_id)
        for row in rows:
            if row.device_id == device_id:
                return row
        raise NotFoundError("Device not found")

    async def summary(self, *, org_id: uuid.UUID) -> ComplianceSummary:
        # Deliberately unpaged: a fleet score computed from one page of devices would be a
        # different number every time you turned the page.
        rows, _ = await self._evaluate(org_id=org_id)
        return self.summarize(rows)

    async def evaluate_all(self, *, org_id: uuid.UUID) -> list[DeviceCompliance]:
        """Every device, scored. For callers that need the scores for more than one purpose
        — the dashboard derives both the fleet summary and the ranked issue list from a
        single pass, because scoring 2,000 devices twice to render one page is not a thing
        to do quietly."""
        rows, _ = await self._evaluate(org_id=org_id)
        return rows

    @staticmethod
    def summarize(rows: list[DeviceCompliance]) -> ComplianceSummary:
        """Aggregate already-scored devices. Split out from summary() so the scoring and the
        counting are separable — the expensive half is the scoring."""
        total = len(rows)
        compliant = sum(1 for r in rows if r.status == "compliant")
        at_risk = sum(1 for r in rows if r.status == "at_risk")
        non_compliant = sum(1 for r in rows if r.status == "non_compliant")
        unknown = sum(1 for r in rows if r.status == "unknown")

        breakdown: list[CheckBreakdown] = []
        for key, label, _ in CHECKS:
            p = f = u = 0
            for r in rows:
                for c in r.checks:
                    if c.key != key:
                        continue
                    if c.status == "pass":
                        p += 1
                    elif c.status == "fail":
                        f += 1
                    else:
                        u += 1
            if p or f or u:  # omit checks that don't apply (e.g. banned list empty)
                breakdown.append(CheckBreakdown(key=key, label=label, passed=p, failed=f, unknown=u))

        # USB posture travels on the device rows, so it is counted in the same pass and both
        # this and the dashboard get it for free. NULL is a device no reporting agent has
        # beaten for yet — unknown, never assumed allowed.
        usb = UsbPosture(
            blocked=sum(1 for r in rows if r.usb_storage_blocked is True),
            allowed=sum(1 for r in rows if r.usb_storage_blocked is False),
            unknown=sum(1 for r in rows if r.usb_storage_blocked is None),
        )

        score = round(compliant / total * 100) if total else 100
        return ComplianceSummary(
            total_devices=total, compliant=compliant, at_risk=at_risk,
            non_compliant=non_compliant, unknown=unknown, score=score, checks=breakdown,
            usb=usb,
        )

    # ── helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _chk(key: str, status: str, detail: str) -> CheckResult:
        return CheckResult(key=key, label=CHECK_LABELS[key], status=status,  # type: ignore[arg-type]
                           detail=detail, fix_action_id=CHECK_FIX[key] if status == "fail" else None)

    def _svc_check(self, key: str, svc: str, device_id, services, have_services) -> CheckResult:
        state = services.get(device_id, {})
        if svc in state:
            running = state[svc].lower() == "running"
            return self._chk(key, "pass" if running else "fail",
                             "Running" if running else f"Stopped ({state[svc]})")
        # Service not seen: unknown (either not collected, or not present on this SKU).
        return self._chk(key, "unknown", "Not reported")


def _min_free_pct(disks) -> float | None:
    """Smallest free-space percentage across a snapshot's disks, or None if unknown."""
    pcts: list[float] = []
    for d in disks or []:
        total = d.get("total_gb") or 0
        free = d.get("free_gb")
        if total and free is not None:
            pcts.append(free / total * 100)
    return min(pcts) if pcts else None
