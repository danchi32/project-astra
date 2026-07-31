"""The dashboard's one payload.

The dashboard used to render counts: devices, online, offline, average CPU. All true, none
of it answering the question someone opens the page with — "is anything wrong, and what do I
do about it". It also showed none of the compliance, fleet-correlation or patch-state work
that already existed, so the platform knew things its home screen didn't.
"""
from datetime import date

from pydantic import BaseModel

from app.schemas.compliance import ComplianceSummary
from app.schemas.fleet import FleetIssue


class DashboardAction(BaseModel):
    """One thing worth doing, phrased as the decision rather than the measurement.

    "3 fixes are waiting for approval" is actionable; "remediation_pending: 3" is a number
    you have to interpret first.
    """

    key: str
    title: str
    detail: str
    count: int
    severity: str      # high | medium | low
    href: str          # where the work actually happens


class PatchState(BaseModel):
    """Updates split by why they are not in effect. These need different responses — only
    one of them is "install it" — so the dashboard never rolls them into one number."""

    pending: int
    awaiting_restart: int
    failed: int
    devices_with_pending: int
    devices_awaiting_restart: int


class TrendPoint(BaseModel):
    """One day of the fleet, from the daily rollups.

    Rollups are the only history that survives — raw snapshots are pruned after a short
    window — so this is what makes the dashboard show a direction rather than a snapshot.
    "12 offline" and "12 offline, up from 3 yesterday" are different facts.
    """

    day: date
    devices_reporting: int
    cpu_avg: float
    disk_free_min_pct: float | None


class DashboardOverview(BaseModel):
    needs_you: list[DashboardAction]
    # Null when the org's plan doesn't include compliance, rather than a zeroed summary —
    # "0% compliant" is a lie, and an empty card invites a support ticket. The portal simply
    # doesn't draw the panel.
    compliance: ComplianceSummary | None = None
    patch: PatchState
    trend: list[TrendPoint]
    top_issues: list[FleetIssue] = []
