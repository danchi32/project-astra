"""L1 — the Free IT Health Check: one report built from what SAVIO already collects.

The sales engine: install the agent on a trial, wait a week, hand the owner a report that
shows their own fleet's problems. So every line here is a count of something real, read from
the same evaluations the portal uses — no estimates, no "₹ at risk" guesses. A section with
nothing to report says so rather than disappearing.
"""
from __future__ import annotations

import re
import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset, Device, DeviceInstalledApp, Organization
from app.models.alert_state import AlertState
from app.models.telemetry import TelemetryDailyRollup
from app.services.compliance import CHECK_LABELS, ComplianceService
from app.services.fleet import _CHECK_ISSUES

REPORT_DAYS = 7
OLD_PC_YEARS = 4

#: Desktop AI tools worth naming in a report (shadow AI). Matched case-insensitively.
AI_TOOL_NAMES = ("chatgpt", "claude", "cursor", "copilot", "ollama", "lm studio", "gpt4all",
                 "perplexity", "windsurf", "jan")

_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}
_DEFAULT_ADVICE = {
    "patch": ("Windows updates missing or failing", "high", None,
              "Push the pending updates from Compliance, and look at any that keep failing."),
}
#: Where Fleet Issues' note is written for the technician (what SAVIO can't push yet), the
#: owner reading this report gets what to do instead.
_REPORT_ADVICE = {
    "defender": "Turn Microsoft Defender back on (Windows Security → Virus & threat protection). "
                "If it keeps stopping, another antivirus or a policy is switching it off — find out which.",
    "firewall": "Turn Windows Firewall back on (Windows Security → Firewall & network protection). "
                "A computer without it accepts connections from anything on the same network.",
}


async def build(session: AsyncSession, org_id: uuid.UUID) -> dict:
    org = await session.get(Organization, org_id)
    rows = await ComplianceService(session).evaluate_all(org_id=org_id)
    summary = ComplianceService.summarize(rows)

    first_day = await session.scalar(
        select(func.min(TelemetryDailyRollup.day)).where(TelemetryDailyRollup.org_id == org_id))
    days = (date.today() - first_day).days + 1 if first_day else 0

    # Findings: one per failing check, worst first, with the machines named.
    findings = []
    for key, label in CHECK_LABELS.items():
        failing = [(r.hostname, c.detail) for r in rows for c in r.checks if c.key == key and c.status == "fail"]
        if not failing:
            continue
        title, severity, _fix, advice = (_CHECK_ISSUES.get(key) or _DEFAULT_ADVICE.get(key)
                                         or (label, "medium", None, None))
        findings.append({
            "key": key, "title": title, "severity": severity, "count": len(failing),
            "devices": [f"{h}: {d}" for h, d in failing[:10]],
            "advice": _REPORT_ADVICE.get(key) or advice or "A one-click fix is available from Fleet Issues.",
        })
    findings.sort(key=lambda f: (_SEVERITY_RANK.get(f["severity"], 1), -f["count"]))

    # Early warning: disks the forecast says will fill within a week.
    filling = [d for (d,) in (await session.execute(
        select(Device.hostname).join(AlertState, AlertState.device_id == Device.id)
        .where(AlertState.org_id == org_id, AlertState.check_key == "disk_forecast",
               AlertState.state == "alerting").order_by(Device.hostname))).all()]

    # Hardware age: purchase date when the asset register has it, else the BIOS date.
    cutoff = (date.today() - timedelta(days=365 * OLD_PC_YEARS)).isoformat()
    purchases = {d: p for d, p in (await session.execute(
        select(Asset.device_id, Asset.purchase_date).where(
            Asset.org_id == org_id, Asset.device_id.is_not(None), Asset.purchase_date.is_not(None)))).all()}
    old = []
    for dev_id, host, bios in (await session.execute(
            select(Device.id, Device.hostname, Device.bios_release_date).where(Device.org_id == org_id))).all():
        when = purchases.get(dev_id) or bios
        if when and when <= cutoff:
            old.append(f"{host} ({when[:4]})")

    today = date.today().isoformat()
    soon = (date.today() + timedelta(days=90)).isoformat()
    warranty = (await session.execute(
        select(Asset.name, Asset.warranty_expiry).where(
            Asset.org_id == org_id, Asset.archived_at.is_(None), Asset.warranty_expiry.is_not(None),
            Asset.warranty_expiry <= soon).order_by(Asset.warranty_expiry))).all()

    apps = (await session.execute(
        select(DeviceInstalledApp.name, DeviceInstalledApp.scope, Device.hostname)
        .join(Device, Device.id == DeviceInstalledApp.device_id)
        .where(DeviceInstalledApp.org_id == org_id))).all()
    ai_tools: dict[str, set[str]] = {}
    for name, _scope, host in apps:
        if any(re.search(rf"\b{re.escape(t)}\b", name.lower()) for t in AI_TOOL_NAMES):
            ai_tools.setdefault(name, set()).add(host)

    return {
        "organization": org.name if org else "",
        "generated_at": date.today().isoformat(),
        "days_of_data": min(days, REPORT_DAYS),
        "complete": days >= REPORT_DAYS,
        "devices": summary.total_devices,
        "score": summary.score,
        "compliant": summary.compliant,
        "at_risk": summary.at_risk,
        "non_compliant": summary.non_compliant,
        "findings": findings,
        "disks_filling_soon": filling,
        "old_hardware": sorted(old),
        "warranty": [{"asset": n, "ends": w, "expired": w < today} for n, w in warranty],
        "software": {
            "distinct_apps": len({n for n, _, _ in apps}),
            "per_user_installs": sum(1 for _, s, _ in apps if s == "user"),
            "ai_tools": [{"name": n, "devices": len(h)} for n, h in sorted(ai_tools.items())],
        },
        "per_device": [{"hostname": r.hostname, "score": r.score, "status": r.status,
                        # Problem titles ("Windows Firewall not running"), not check names,
                        # which read as passes ("Windows Firewall running") under "failing".
                        "failed": [(_CHECK_ISSUES.get(c.key) or _DEFAULT_ADVICE.get(c.key) or (c.label,))[0]
                                   for c in r.checks if c.status == "fail"]}
                       for r in sorted(rows, key=lambda r: (r.score, r.hostname))],
    }
