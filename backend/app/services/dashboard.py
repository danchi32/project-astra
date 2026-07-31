"""Everything the dashboard shows, assembled in one pass.

The fleet is scored ONCE here and both the compliance summary and the ranked issue list are
derived from that pass. Calling the two existing endpoints instead would score every device
twice per page load — invisible at ten devices, and the dominant cost of the home screen at
two thousand.
"""
import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, DeviceWindowsUpdate, RemediationStatus, RemediationTask
from app.models.base import utcnow
from app.models.telemetry import (
    UPDATE_FAILED,
    UPDATE_PENDING,
    UPDATE_PENDING_RESTART,
    TelemetryDailyRollup,
)
from app.schemas.compliance import ComplianceSummary
from app.schemas.dashboard import (
    DashboardAction,
    DashboardOverview,
    PatchState,
    TrendPoint,
)
from app.schemas.devices import ONLINE_THRESHOLD
from app.services.compliance import ComplianceService
from app.services.entitlements import COMPLIANCE, FLEET_CORRELATION
from app.services.fleet import FleetService

TREND_DAYS = 14
TOP_ISSUES = 3


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def overview(self, *, org_id: uuid.UUID) -> DashboardOverview:
        """The dashboard aggregates compliance and fleet data by calling those services
        directly, so the routers' entitlement gates don't apply here. Checked explicitly:
        gating the compliance page while the same numbers arrive on the home screen would
        have been a gate in name only.
        """
        granted = await self._features(org_id)
        show_compliance = COMPLIANCE in granted
        show_issues = FLEET_CORRELATION in granted

        summary = None
        issues: list = []
        if show_compliance or show_issues:
            rows = await ComplianceService(self.session).evaluate_all(org_id=org_id)
            if show_compliance:
                summary = ComplianceService.summarize(rows)
            if show_issues:
                issues = await FleetService(self.session).issues(org_id=org_id, compliance=rows)

        patch = await self._patch_state(org_id)

        return DashboardOverview(
            needs_you=await self._needs_you(org_id, summary, patch, issues),
            compliance=summary,
            patch=patch,
            trend=await self._trend(org_id),
            # Ranked by how many devices each affects, which is the order they were already
            # sorted in — the top three are the ones worth a home-screen slot.
            top_issues=issues[:TOP_ISSUES],
        )

    async def _features(self, org_id: uuid.UUID) -> frozenset[str]:
        from app.models import Organization
        from app.services.entitlements import features_for

        org = await self.session.get(Organization, org_id)
        if org is None:
            return frozenset()
        return features_for(org.plan, org.entitlement_overrides)

    async def _patch_state(self, org_id: uuid.UUID) -> PatchState:
        rows = (await self.session.execute(
            select(
                DeviceWindowsUpdate.state,
                func.count(),
                func.count(func.distinct(DeviceWindowsUpdate.device_id)),
            )
            .where(DeviceWindowsUpdate.org_id == org_id)
            .group_by(DeviceWindowsUpdate.state)
        )).all()
        by_state = {r[0]: (int(r[1]), int(r[2])) for r in rows}
        return PatchState(
            pending=by_state.get(UPDATE_PENDING, (0, 0))[0],
            awaiting_restart=by_state.get(UPDATE_PENDING_RESTART, (0, 0))[0],
            failed=by_state.get(UPDATE_FAILED, (0, 0))[0],
            devices_with_pending=by_state.get(UPDATE_PENDING, (0, 0))[1],
            devices_awaiting_restart=by_state.get(UPDATE_PENDING_RESTART, (0, 0))[1],
        )

    async def _trend(self, org_id: uuid.UUID) -> list[TrendPoint]:
        since = (utcnow() - timedelta(days=TREND_DAYS)).date()
        rows = (await self.session.execute(
            select(
                TelemetryDailyRollup.day,
                func.count(func.distinct(TelemetryDailyRollup.device_id)),
                func.avg(TelemetryDailyRollup.cpu_avg),
                func.min(TelemetryDailyRollup.disk_free_min_pct),
            )
            .where(TelemetryDailyRollup.org_id == org_id, TelemetryDailyRollup.day >= since)
            .group_by(TelemetryDailyRollup.day)
            .order_by(TelemetryDailyRollup.day)
        )).all()
        return [
            TrendPoint(
                day=r[0],
                # Devices that reported at all that day. A device with no rollup row was
                # silent — which is the fact worth trending on a fleet dashboard.
                devices_reporting=int(r[1]),
                cpu_avg=round(float(r[2] or 0.0), 1),
                disk_free_min_pct=round(float(r[3]), 1) if r[3] is not None else None,
            )
            for r in rows
        ]

    async def _needs_you(
        self,
        org_id: uuid.UUID,
        summary: ComplianceSummary | None,
        patch: PatchState,
        issues: list,
    ) -> list[DashboardAction]:
        """The decisions, highest-consequence first.

        Only things a person can act on today appear here. A dashboard that lists everything
        it knows is a dashboard nobody reads twice, so a quiet fleet returns an empty list
        and the UI says so rather than padding it out.
        """
        actions: list[DashboardAction] = []

        pending_approvals = int(await self.session.scalar(
            select(func.count()).select_from(RemediationTask).where(
                RemediationTask.org_id == org_id,
                RemediationTask.status == RemediationStatus.PENDING_APPROVAL,
            )
        ) or 0)
        if pending_approvals:
            actions.append(DashboardAction(
                key="approvals",
                title=f"{pending_approvals} fix{'es' if pending_approvals != 1 else ''} waiting for approval",
                detail="Nothing runs on a device until someone clears it.",
                count=pending_approvals, severity="high", href="/self-healing",
            ))

        if patch.failed:
            actions.append(DashboardAction(
                key="failed_updates",
                title=f"{patch.failed} update{'s' if patch.failed != 1 else ''} failing to install",
                detail="Windows reported an error code — a repeat failure needs a cause, not a retry.",
                count=patch.failed, severity="high", href="/fleet",
            ))

        if patch.devices_awaiting_restart:
            n = patch.devices_awaiting_restart
            actions.append(DashboardAction(
                key="awaiting_restart",
                title=f"{n} device{'s' if n != 1 else ''} one restart from being patched",
                detail="The updates are installed; only a reboot applies them.",
                count=n, severity="medium", href="/compliance",
            ))

        if summary is not None and summary.non_compliant:
            actions.append(DashboardAction(
                key="non_compliant",
                title=f"{summary.non_compliant} device{'s' if summary.non_compliant != 1 else ''} failing more than one check",
                detail="Open compliance to see which checks and push the fixes.",
                count=summary.non_compliant, severity="high", href="/compliance",
            ))

        # Devices that have stopped checking in. Distinct from "offline" on the device list:
        # this is the count that means the agent may be broken or quarantined, which is the
        # one failure that makes every other number on this page stale.
        cutoff = utcnow() - ONLINE_THRESHOLD
        silent = int(await self.session.scalar(
            select(func.count()).select_from(Device).where(
                Device.org_id == org_id,
                Device.is_active.is_(True),
                (Device.last_seen_at.is_(None)) | (Device.last_seen_at < cutoff),
            )
        ) or 0)
        if silent:
            actions.append(DashboardAction(
                key="silent_devices",
                title=f"{silent} device{'s' if silent != 1 else ''} not checking in",
                detail="ASTRA can't see or fix a device that isn't reporting.",
                count=silent, severity="medium" if silent < 5 else "high", href="/devices",
            ))

        order = {"high": 0, "medium": 1, "low": 2}
        actions.sort(key=lambda a: (order.get(a.severity, 3), -a.count))
        return actions
