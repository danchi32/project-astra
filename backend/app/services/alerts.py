"""N1 — early-warning alerts, evaluated as telemetry arrives.

Before this, problems showed up only when someone opened the portal; nothing pushed and
nothing predicted. Two kinds of alert now:

* **Turned bad** — Defender or the firewall stopped, disk below 10 % free, critical errors,
  restricted software, Windows not activated, a cracked activation.
* **Will turn bad** — the disk-fill forecast: the slope of free disk space over the last
  14 days of daily rollups says when the disk runs out. This is the one alert that really is
  "before it happens".

Everything is edge-triggered through ``AlertState``: an alert fires when a check goes from
healthy to alerting and a quiet "recovered" when it comes back — never every minute while a
problem lasts. Checks are only evaluated when this push carries their data (services and
licensing come hourly; disks and events every minute), so a push without inventory can't
make an inventory alert "recover". No scheduler: things that need one (a device gone
silent, a warranty ending) are N2.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BannedSoftware, Device, NotificationCategory, NotificationSeverity
from app.models.alert_state import AlertState
from app.models.base import utcnow
from app.models.telemetry import TelemetryDailyRollup
from app.schemas.telemetry import TelemetryPush
from app.services.licensing import activation_tool_findings, windows_activation
from app.services.notifications import NotificationService

log = logging.getLogger(__name__)

DISK_LOW_PCT = 10.0        # the compliance threshold
DISK_CRITICAL_PCT = 5.0
DISK_RECOVER_PCT = 12.0    # hysteresis: 9.9 ↔ 10.1 % must not flap an alert on and off
FORECAST_WINDOW_DAYS = 14
FORECAST_MIN_POINTS = 5
FORECAST_WARN_DAYS = 7
FORECAST_CRITICAL_DAYS = 2


@dataclass
class Finding:
    bad: bool
    title: str
    detail: str
    critical: bool = False


@dataclass
class Fired:
    """A critical alert that turned on during this push — the caller emails these after the
    ingest commits."""
    device: Device
    title: str
    detail: str


def disk_days_left(points: list[tuple[int, float]]) -> float | None:
    """Days until free space reaches zero, by least squares over (day_index, free_pct).

    None when there isn't enough history or free space isn't falling — a flat or growing
    disk never alerts.
    """
    if len(points) < FORECAST_MIN_POINTS:
        return None
    n = len(points)
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    var = sum((x - mx) ** 2 for x, _ in points)
    if var == 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in points) / var  # % per day
    if slope >= -0.05:      # losing under 0.05 %/day is noise, not a trend
        return None
    _, current = max(points)          # free % on the most recent day
    return max(0.0, current / -slope)


class AlertService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def evaluate(self, *, device: Device, data: TelemetryPush) -> list[Fired]:
        findings = await self._findings(device, data)
        if not findings:
            return []

        states = {s.check_key: s for s in (await self.session.execute(
            select(AlertState).where(AlertState.device_id == device.id)
        )).scalars()}
        notify = NotificationService(self.session)
        fired: list[Fired] = []
        now = utcnow()
        for key, f in findings.items():
            st = states.get(key)
            alerting = st is not None and st.state == "alerting"
            if f.bad and not alerting:
                if st is None:
                    st = AlertState(device_id=device.id, org_id=device.org_id, check_key=key,
                                    state="alerting", since=now)
                    self.session.add(st)
                st.state, st.since, st.detail = "alerting", now, f.detail[:300]
                await notify.notify(
                    org_id=device.org_id, category=NotificationCategory.TELEMETRY,
                    severity=NotificationSeverity.CRITICAL if f.critical else NotificationSeverity.WARNING,
                    title=f"{device.hostname}: {f.title}", message=f.detail,
                    link=f"/devices/{device.id}",
                )
                if f.critical:
                    fired.append(Fired(device=device, title=f.title, detail=f.detail))
            elif not f.bad and alerting:
                st.state, st.since, st.detail = "ok", now, None
                await notify.notify(
                    org_id=device.org_id, category=NotificationCategory.TELEMETRY,
                    severity=NotificationSeverity.INFO,
                    title=f"{device.hostname}: resolved — {f.title}",
                    message="Back to normal.", link=f"/devices/{device.id}",
                )
        await self.session.flush()
        return fired

    async def _findings(self, device: Device, data: TelemetryPush) -> dict[str, Finding]:
        out: dict[str, Finding] = {}

        # Disk — every push. Hysteresis via the previous state is applied by asking for a
        # higher bar to clear an alert than to raise it.
        worst = None
        for d in data.disks:
            if d.total_gb and d.total_gb > 0:
                pct = d.free_gb / d.total_gb * 100
                if worst is None or pct < worst[1]:
                    worst = (d.drive, pct)
        if worst is not None:
            drive, pct = worst
            prev = (await self.session.execute(select(AlertState.state).where(
                AlertState.device_id == device.id, AlertState.check_key == "disk_low"))).scalar()
            bar = DISK_RECOVER_PCT if prev == "alerting" else DISK_LOW_PCT
            out["disk_low"] = Finding(bad=pct < bar, title="disk almost full",
                                      detail=f"{drive} has {pct:.0f}% free.",
                                      critical=pct < DISK_CRITICAL_PCT)

        # Critical events — every push (the agent sends its recent window each time).
        crit = [e for e in data.event_logs if e.level == "Critical"]
        out["critical_events"] = Finding(
            bad=bool(crit), title="critical system errors",
            detail=f"{len(crit)} critical event(s), e.g. {crit[0].source} {crit[0].event_id}."
            if crit else "", critical=True)

        # Services — hourly inventory only.
        if data.services:
            state = {s.name.lower(): s.status for s in data.services}
            for key, svc, label in (("defender_off", "windefend", "Microsoft Defender"),
                                    ("firewall_off", "mpssvc", "Windows Firewall")):
                if svc in state:
                    stopped = state[svc].lower() != "running"
                    out[key] = Finding(bad=stopped, title=f"{label} not running",
                                       detail=f"{label} is {state[svc]}.", critical=True)

        # Restricted software — hourly inventory only.
        if data.installed_apps:
            patterns = [p.lower() for p in (await self.session.execute(
                select(BannedSoftware.pattern).where(BannedSoftware.org_id == device.org_id)
            )).scalars() if p]
            hits = sorted({a.name for a in data.installed_apps
                           if any(p in a.name.lower() for p in patterns)})
            if patterns:
                out["banned_software"] = Finding(bad=bool(hits), title="restricted software installed",
                                                 detail=", ".join(hits[:5]))

        # Activation — when the push carries licensing (hourly, agent 0.14+).
        if data.licensing is not None:
            status, detail = windows_activation(data.licensing)
            if status != "unknown":
                out["not_activated"] = Finding(bad=status == "fail", title="Windows not activated",
                                               detail=detail)
            names = [a.name for a in data.installed_apps] + [s.name for s in data.services] + \
                [s.display_name for s in data.services]
            cracks = activation_tool_findings(data.licensing, names, device.hostname)
            out["cracked_activation"] = Finding(bad=bool(cracks), title="cracked activation detected",
                                                detail="; ".join(cracks[:3]), critical=True)

        # Disk-fill forecast — once an hour is plenty (it reads daily rollups).
        if data.installed_apps or data.services:
            rows = (await self.session.execute(
                select(TelemetryDailyRollup.day, TelemetryDailyRollup.disk_free_min_pct)
                .where(TelemetryDailyRollup.device_id == device.id,
                       TelemetryDailyRollup.disk_free_min_pct.is_not(None))
                .order_by(TelemetryDailyRollup.day.desc()).limit(FORECAST_WINDOW_DAYS)
            )).all()
            if rows:
                first = min(day for day, _ in rows)
                days = disk_days_left([((day - first).days, pct) for day, pct in rows])
                # Rounded, as it is shown: "about 7 days" must warn, float dust or not.
                bad = days is not None and round(days) <= FORECAST_WARN_DAYS
                out["disk_forecast"] = Finding(
                    bad=bad, title="disk will fill up soon",
                    detail=(f"At the current rate a disk will be full in about {max(1, round(days))} "
                            f"day(s).") if bad else "",
                    critical=bad and round(days) <= FORECAST_CRITICAL_DAYS)
        return out


async def email_critical_alerts(session: AsyncSession, org_id, fired: list[Fired]) -> None:
    """Email the org's admins about critical alerts that just turned on. After the ingest has
    committed, best-effort: a mail outage must not fail a device's telemetry push, and the
    in-app notification already exists either way. Off when the org says so."""
    from app.core.config import get_settings
    from app.models import OrganizationSettings, User, UserRole
    from app.services.email import EmailService, _shell

    try:
        opted_out = (await session.execute(
            select(OrganizationSettings.email_critical_alerts)
            .where(OrganizationSettings.org_id == org_id))).scalar() is False
        if opted_out:
            return
        admins = (await session.execute(select(User.email).where(
            User.org_id == org_id, User.role == UserRole.ADMIN, User.is_active.is_(True)
        ))).scalars().all()
        if not admins:
            return
        portal = (get_settings().public_app_url or "").rstrip("/")
        items = "".join(
            f"<li><b>{f.device.hostname}</b>: {f.title} — {f.detail}"
            + (f' <a href="{portal}/devices/{f.device.id}">Open</a>' if portal else "")
            + "</li>"
            for f in fired)
        subject = (f"SAVIO alert: {fired[0].device.hostname} — {fired[0].title}" if len(fired) == 1
                   else f"SAVIO: {len(fired)} critical alerts")
        html = _shell("Critical alert", f"<ul>{items}</ul><p style=\"color:#666\">You get this "
                      "because you are an admin. Turn these emails off in Settings → Organization.</p>")
        email = EmailService()
        for to in admins:
            await email.send(to=to, subject=subject, html=html)
    except Exception:
        log.exception("could not email critical alerts for org %s", org_id)
