"""Phase 3b · J3 Board report and J4 Compliance pack: printable pages built from what SAVIO
already records, nothing estimated and nothing written by a model.

- J3, the board report: a month or a quarter on one page for the owner or the board. The
  headline numbers, the brief's sections for the period (J1), the top risks from the health
  check (L1), and, with AI Guard, DPDP readiness and breach records (I1). Counts only, never a
  person's name, so staff can print it.
- J4, the compliance pack: the evidence an auditor, insurer or client asks for, in one place:
  endpoint security per PC (F1), who can do what (roles), the record of changes (the audit log),
  and data protection (I1). Admin only: it names staff and PCs.

Both say what SAVIO's records show, never that a standard or law is met.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, GuardIncident, Organization, User
from app.models.base import as_utc, utcnow
from app.services import brief, health_check
from app.services.browser_policy import entitled
from app.services.compliance import ComplianceService
from app.services.reports import ReportService

PERIODS = {30: "month", 90: "quarter"}
TOP_RISKS = 5
TOP_CHANGES = 15
NOT_A_CERTIFICATE = ("This shows what SAVIO's own records hold for the period. It is evidence, not a certificate: "
                     "it does not say that any standard, contract or law is met.")


async def _breaches(session: AsyncSession, org_id, since) -> dict:
    rows = (await session.execute(select(GuardIncident).where(GuardIncident.org_id == org_id)
                                  .order_by(GuardIncident.found_at.desc()))).scalars().all()
    return {
        "found": sum(1 for r in rows if as_utc(r.found_at) >= since),
        "open": sum(1 for r in rows if r.status == "open"),
        "records": rows,
    }


async def board(session: AsyncSession, *, actor: User, days: int) -> dict:
    org_id = actor.org_id
    period = PERIODS[days]
    b = await brief.build(session, actor=actor, period=period)
    hc = await health_check.build(session, org_id)
    value = await ReportService(session).value_report(actor=actor, days=days)
    kpis = {"devices": hc["devices"], "health_score": hc["score"], "fixed_unattended": value.fixed_unattended,
            "hours_saved": value.hours_saved, "inr_saved": value.inr_saved,
            "dpdp_score": None, "breaches_found": None, "breaches_open": None}
    if await entitled(session, org_id):
        from app.services import dpdp

        kpis["dpdp_score"] = (await dpdp.readiness(session, org_id))["score"]
        br = await _breaches(session, org_id, b["since"])
        kpis["breaches_found"], kpis["breaches_open"] = br["found"], br["open"]
    return {
        "organization": hc["organization"], "period_days": days, "since": b["since"], "generated_at": b["generated_at"],
        "title": f"Board report: {period}", "headline": b["headline"], "kpis": kpis,
        "sections": b["sections"],
        "risks": [{k: f[k] for k in ("title", "severity", "count", "advice")} for f in hc["findings"][:TOP_RISKS]],
        "footer": b["footer"],
    }


async def pack(session: AsyncSession, *, actor: User, days: int) -> dict:
    org_id = actor.org_id
    now = utcnow()
    since = now - timedelta(days=days)
    org = await session.get(Organization, org_id)

    rows = await ComplianceService(session).evaluate_all(org_id=org_id)
    s = ComplianceService.summarize(rows)
    security = {
        "devices": s.total_devices, "security_score": s.security_score, "compliant": s.compliant,
        "at_risk": s.at_risk, "non_compliant": s.non_compliant, "unknown": s.unknown,
        "checks": [c.model_dump() for c in s.checks], "usb": s.usb.model_dump(),
        "per_device": [{"hostname": r.hostname, "score": r.score, "status": r.status,
                        "failed": [c.label for c in r.checks if c.status == "fail"]}
                       for r in sorted(rows, key=lambda r: (r.score, r.hostname))],
    }

    users = (await session.execute(select(User.full_name, User.role, User.is_active)
                                   .where(User.org_id == org_id).order_by(User.full_name))).all()
    access = {
        "by_role": {r: sum(1 for u in users if u.is_active and u.role.value == r) for r in ("admin", "technician", "user")},
        "inactive": sum(1 for u in users if not u.is_active),
        "staff": [{"name": u.full_name, "role": u.role.value} for u in users
                  if u.is_active and u.role.value in ("admin", "technician")],
    }

    by_action = (await session.execute(
        select(AuditLog.action, func.count()).where(AuditLog.org_id == org_id, AuditLog.created_at >= since)
        .group_by(AuditLog.action).order_by(func.count().desc(), AuditLog.action))).all()
    changes = {"total": sum(n for _, n in by_action),
               "by_action": [{"action": a, "count": n} for a, n in by_action[:TOP_CHANGES]]}

    data_protection = None
    if await entitled(session, org_id):
        from app.services import dpdp

        r = await dpdp.readiness(session, org_id)
        br = await _breaches(session, org_id, since)
        data_protection = {
            "score": r["score"], "done": r["done"], "total": r["total"],
            "items": [{k: i[k] for k in ("title", "status", "detail")} for i in r["items"]],
            "contact": r["contact"], "retention": r["retention"],
            "breaches": [{"title": i.title, "found_at": i.found_at, "status": i.status,
                          "steps_settled": len(i.steps)} for i in br["records"] if as_utc(i.found_at) >= since or i.status == "open"],
        }

    return {
        "organization": org.name if org else "", "period_days": days, "since": since, "generated_at": now,
        "security": security, "access": access, "changes": changes, "data_protection": data_protection,
        "disclaimer": NOT_A_CERTIFICATE,
    }
