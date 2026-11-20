"""J1 · Brief: the day or the week for whoever runs IT, in plain business language.

On demand (the 2.0 decision, 16 Nov): read it in the portal, or e-mail it to yourself now.
Nothing here runs on a clock. When a client wants it in their inbox every morning, a
scheduler calls `build` and `send` unchanged.

Every line is a count of something SAVIO recorded, taken from the reports that already
exist: the Value report (J5), AI safety (C3), Recommendations (J2), compliance (F1),
rollouts (C2). No sentence is written by a model, so the brief cannot say something the
data does not.
"""
from __future__ import annotations

import html
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset, AuditLog, Device, RemediationStatus, RemediationTask, User
from app.models.base import as_utc, utcnow
from app.models.deployment import Deployment
from app.schemas.devices import ONLINE_THRESHOLD
from app.services.audit import AuditService
from app.services.compliance import ComplianceService
from app.services.exceptions import ConflictError
from app.services.recommendations import RecommendationService
from app.services.reports import ReportService

PERIOD_DAYS = {"day": 1, "week": 7, "month": 30, "quarter": 90}   # month / quarter: J3's board report
SILENT_AFTER = timedelta(hours=24)
WARRANTY_SOON_DAYS = 30
MAX_EMAILS_PER_HOUR = 5

# Sentence templates.
T = {
    "title_day": "Your IT today", "title_week": "Your IT this week",
    "title_month": "Your IT this month", "title_quarter": "Your IT this quarter",
    "fleet": "Computers", "security": "Security", "healing": "Fixed by SAVIO",
    "attention": "Needs your attention", "next": "Recommended next",
    "devices": "{n} computers, {online} online now.",
    "new_devices": "{n} new computer(s) joined.",
    "silent": "{n} computer(s) have not checked in for over a day.",
    "score": "Security score: {score}%.",
    "score_unknown": "Security score: not known yet (no computer has reported its security state).",
    "fixed": "{n} problem(s) fixed with nobody needing to step in.",
    "fixed_none": "No problems needed fixing on their own.",
    "hours": "That is about {hours} hours of IT work saved.",
    "inr": "Worth about ₹{inr}, at your hourly IT cost.",
    "proven": "{n} of those fixes were measured and shown to work.",
    "failed": "{n} fix(es) did not work and may need a person.",
    "pending": "{n} fix(es) are waiting for someone to approve them.",
    "held": "{n} AI suggestion(s) were held for a person because they leaned on text from a computer.",
    "refused": "{n} AI request(s) were refused because the assistant may not do that.",
    "halted": "{n} software rollout(s) were stopped by the safety check.",
    "warranty": "{n} warranty(ies) end in the next {days} days.",
    "nothing": "Nothing needs your attention.",
    "rec": "{title} ({count} affected)",
    "headline_ok": "All quiet: {fixed} fixed automatically, nothing waiting on you.",
    "headline_attention": "{fixed} fixed automatically; {attention} thing(s) need your attention.",
    "footer": "Every number here comes from SAVIO's own records for this period.",
    "risk": {"high": "high risk", "medium": "medium risk", "low": "low risk"},
    # S5: AI Guard. Counts only; never a person's name.
    "guard": "AI Guard",
    "cases": "{n} case(s) opened: {high} high, {medium} medium, {low} low.",
    "cases_none": "No new cases: nobody's handling of sensitive data stood out.",
    "stopped": "Sensitive data was stopped {blocked} time(s) and hidden {hidden} time(s).",
    "went_ahead": "People went ahead after a warning {n} time(s).",
    "trend_up": "That is {n} more event(s) with sensitive data than the period before.",
    "trend_down": "That is {n} fewer event(s) with sensitive data than the period before.",
    "usb": "{n} copy(ies) to USB drives held sensitive data.",
    "closed": "Other browsers were closed {n} time(s).",
    "recognised": "SAVIO recognised {n} new site(s) your people used.",
    "suggests": "SAVIO suggests: {title}.",
    "high_open": "{n} high-risk AI Guard case(s) are open (AI Guard → Cases).",
    "requests": "{n} request(s) are waiting for IT approval in AI Guard.",
}


async def build(session: AsyncSession, *, actor: User, period: str) -> dict:
    t = T
    days = PERIOD_DAYS[period]
    now = utcnow()
    since = now - timedelta(days=days)
    org_id = actor.org_id

    devices = (await session.execute(
        select(Device.last_seen_at, Device.created_at).where(Device.org_id == org_id,
                                                             Device.is_active.is_(True)))).all()
    online = sum(1 for seen, _ in devices if seen and now - as_utc(seen) < ONLINE_THRESHOLD)
    # Silent for a day: last seen over 24 h ago, or enrolled over 24 h ago and never seen.
    # A PC enrolled this morning that has not reported yet is not "silent".
    silent = sum(1 for seen, created in devices
                 if now - as_utc(seen or created) > SILENT_AFTER)
    joined = sum(1 for _, created in devices if as_utc(created) >= since)

    summary = ComplianceService.summarize(await ComplianceService(session).evaluate_all(org_id=org_id))
    reports = ReportService(session)
    value = await reports.value_report(actor=actor, days=days)
    safety = await reports.ai_safety_report(actor=actor, days=days)
    failed = await session.scalar(select(func.count()).select_from(RemediationTask).where(
        RemediationTask.org_id == org_id, RemediationTask.status == RemediationStatus.FAILED,
        RemediationTask.completed_at >= since))
    pending = await session.scalar(select(func.count()).select_from(RemediationTask).where(
        RemediationTask.org_id == org_id, RemediationTask.status == RemediationStatus.PENDING_APPROVAL))
    halted = await session.scalar(select(func.count()).select_from(Deployment).where(
        Deployment.org_id == org_id, Deployment.halted_at >= since))
    today = date.today()
    warranty = await session.scalar(select(func.count()).select_from(Asset).where(
        Asset.org_id == org_id, Asset.archived_at.is_(None), Asset.warranty_expiry.is_not(None),
        Asset.warranty_expiry >= today.isoformat(),
        Asset.warranty_expiry <= (today + timedelta(days=WARRANTY_SOON_DAYS)).isoformat()))
    recs, _ = await RecommendationService(session).list(actor=actor, status="open")

    fleet = [t["devices"].format(n=len(devices), online=online)]
    if joined:
        fleet.append(t["new_devices"].format(n=joined))
    security = [t["score"].format(score=summary.security_score) if summary.security_score is not None
                else t["score_unknown"]]
    healing = [t["fixed"].format(n=value.fixed_unattended) if value.fixed_unattended else t["fixed_none"]]
    if value.fixed_unattended:
        healing.append(t["hours"].format(hours=value.hours_saved))
        if value.inr_saved:
            healing.append(t["inr"].format(inr=f"{value.inr_saved:,}"))
        if value.proven_improved:
            healing.append(t["proven"].format(n=value.proven_improved))

    attention = []
    for key, n, extra in (("failed", failed, {}), ("pending", pending, {}), ("silent", silent, {}),
                          ("held", safety.raised, {}), ("refused", safety.refused, {}),
                          ("halted", halted, {}), ("warranty", warranty, {"days": WARRANTY_SOON_DAYS})):
        if n:
            attention.append(t[key].format(n=n, **extra))
    guard, guard_attention = await _guard(session, org_id, since, days)
    attention += guard_attention
    next_steps = [f"{t['rec'].format(title=r.title, count=(r.evidence or {}).get('count', 0))} · "
                  f"{t['risk'].get(r.risk, r.risk)}" for r in recs[:3]]

    headline = (t["headline_attention"].format(fixed=value.fixed_unattended, attention=len(attention))
                if attention else t["headline_ok"].format(fixed=value.fixed_unattended))
    sections = [
        {"key": "fleet", "title": t["fleet"], "lines": fleet},
        {"key": "security", "title": t["security"], "lines": security},
        {"key": "healing", "title": t["healing"], "lines": healing},
        {"key": "attention", "title": t["attention"], "lines": attention or [t["nothing"]]},
    ]
    if guard:
        sections.insert(3, {"key": "guard", "title": t["guard"], "lines": guard})
    if next_steps:
        sections.append({"key": "next", "title": t["next"], "lines": next_steps})
    return {
        "period": period, "since": since, "generated_at": now,
        "title": t[f"title_{period}"], "headline": headline, "sections": sections,
        "footer": t["footer"],
    }


async def _guard(session: AsyncSession, org_id, since, days: int) -> tuple[list[str], list[str]]:
    """S5: the period in AI Guard, for an org that has it. (lines, attention lines). Counts only:
    the brief also goes to technicians, and cases name people, so it never does."""
    from app.models import GuardApproval, GuardCase, GuardEvent, LearnedCategory
    from app.services import guard_approvals, guard_events, guard_sites, guard_suggestions
    from app.services.browser_policy import entitled

    if not await entitled(session, org_id):
        return [], []
    t = T
    lines: list[str] = []
    levels = dict((await session.execute(select(GuardCase.level, func.count()).where(
        GuardCase.org_id == org_id, GuardCase.opened_at >= since).group_by(GuardCase.level))).all())
    opened = sum(levels.values())
    lines.append(t["cases"].format(n=opened, high=levels.get("high", 0), medium=levels.get("medium", 0),
                                   low=levels.get("low", 0)) if opened else t["cases_none"])
    s = await guard_events.summary(session, org_id, days)
    if s["blocked"] or s["redacted"]:
        lines.append(t["stopped"].format(blocked=s["blocked"], hidden=s["redacted"]))
    if s["went_ahead"]:
        lines.append(t["went_ahead"].format(n=s["went_ahead"]))
    before = (await guard_events.summary(session, org_id, days * 2))["total"] - s["total"]
    if s["total"] != before and (s["total"] or before):
        diff = s["total"] - before
        lines.append(t["trend_up" if diff > 0 else "trend_down"].format(n=abs(diff)))
    usb = await session.scalar(select(func.count()).select_from(GuardEvent).where(
        GuardEvent.org_id == org_id, GuardEvent.channel == "usb", GuardEvent.occurred_at >= since))
    if usb:
        lines.append(t["usb"].format(n=usb))
    closed = sum(sum((a.detail or {}).get("closed", {}).values()) for a in (await session.execute(
        select(AuditLog).where(AuditLog.org_id == org_id, AuditLog.action == "guard.other_browser_closed",
                               AuditLog.created_at >= since))).scalars())
    if closed:
        lines.append(t["closed"].format(n=closed))
    sites = set((await session.execute(select(GuardEvent.site).where(
        GuardEvent.org_id == org_id, GuardEvent.occurred_at >= since).distinct())).scalars())
    learned_now = set((await session.execute(select(LearnedCategory.key).where(
        LearnedCategory.kind == guard_sites.LEARNED_KIND, LearnedCategory.created_at >= since))).scalars())
    recognised = {guard_sites.registrable(x) for x in sites} & learned_now
    if recognised:
        lines.append(t["recognised"].format(n=len(recognised)))
    for card in (await guard_suggestions.suggestions(session, org_id))[:2]:
        lines.append(t["suggests"].format(title=card["title"]))

    attention: list[str] = []
    high_open = await session.scalar(select(func.count()).select_from(GuardCase).where(
        GuardCase.org_id == org_id, GuardCase.status == "open", GuardCase.level == "high"))
    if high_open:
        attention.append(t["high_open"].format(n=high_open))
    waiting = await session.scalar(select(func.count()).select_from(GuardApproval).where(
        GuardApproval.org_id == org_id, GuardApproval.status == "pending",
        GuardApproval.requested_at >= utcnow() - guard_approvals.PENDING_FOR))
    if waiting:
        attention.append(t["requests"].format(n=waiting))
    return lines, attention


def render_html(brief: dict) -> str:
    """Every value escaped: recommendation titles carry asset and device names."""
    from app.services.email import _shell

    e = html.escape
    body = f'<p style="font-size:15px;font-weight:600">{e(brief["headline"])}</p>'
    for s in brief["sections"]:
        items = "".join(f"<li>{e(line)}</li>" for line in s["lines"])
        body += f'<h2 style="font-size:14px;margin:16px 0 4px">{e(s["title"])}</h2><ul style="margin:0">{items}</ul>'
    body += f'<p style="color:#666;font-size:12px;margin-top:16px">{e(brief["footer"])}</p>'
    return _shell(e(brief["title"]), body)


async def send(session: AsyncSession, *, actor: User, period: str) -> tuple[bool, str]:
    """E-mail the brief to the person asking, and only them: never a list typed into a box."""
    from app.services.email import EmailService

    recent = await session.scalar(select(func.count()).select_from(AuditLog).where(
        AuditLog.org_id == actor.org_id, AuditLog.actor_id == actor.id,
        AuditLog.action == "report.brief_emailed", AuditLog.created_at >= utcnow() - timedelta(hours=1)))
    if recent >= MAX_EMAILS_PER_HOUR:
        raise ConflictError(f"At most {MAX_EMAILS_PER_HOUR} briefs an hour. Try again later.")
    to = actor.email
    # Recorded (and committed) before the slow build and send, so parallel requests see each
    # other in the count instead of all passing it at once.
    await AuditService(session).record(
        org_id=actor.org_id, actor_id=actor.id, action="report.brief_emailed",
        target_type="organization", target_id=str(actor.org_id), detail={"period": period},
    )
    await session.commit()
    brief = await build(session, actor=actor, period=period)
    sent = await EmailService().send(to=to, subject=f"SAVIO · {brief['title']}", html=render_html(brief))
    return sent, to
