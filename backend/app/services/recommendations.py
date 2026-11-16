"""J2 · Recommendations: what SAVIO suggests the org do next, each with its evidence.

Built from data SAVIO already has, the same evaluations the portal and the Health Check use:
failing compliance checks (F1 security and L2 activation included), disks forecast to fill,
warranties ending, and old hardware. Nothing is estimated that cannot be traced. The time
figure is "PCs affected x the org's own minutes per fix", and the rupee figure is that time
x the org's own hourly cost. With no hourly cost set, no rupee figure is shown.

Refreshed whenever the list is read, so no scheduler is needed (the 2.0 decision's
option b, for this module).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset, Device, Recommendation, User
from app.models.alert_state import AlertState
from app.models.base import utcnow
from app.services.audit import AuditService
from app.services.compliance import CHECK_LABELS, ComplianceService
from app.services.exceptions import ConflictError, NotFoundError
from app.services.fleet import _CHECK_ISSUES
from app.services.health_check import _DEFAULT_ADVICE, _REPORT_ADVICE, OLD_PC_YEARS
from app.services.settings import SettingsService

WARRANTY_DAYS = 90
_RISK_RANK = {"high": 0, "medium": 1, "low": 2}


@dataclass
class Finding:
    key: str
    title: str
    devices: list[str]
    risk: str
    effort: str
    advice: str
    action_id: str | None = None
    detail: str | None = None
    per_device_work: bool = True


class RecommendationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _findings(self, org_id: uuid.UUID) -> list[Finding]:
        out: list[Finding] = []
        rows = await ComplianceService(self.session).evaluate_all(org_id=org_id)
        for key, label in CHECK_LABELS.items():
            failing = [f"{r.hostname}: {c.detail}" for r in rows for c in r.checks
                       if c.key == key and c.status == "fail"]
            if not failing:
                continue
            title, risk, fix, note = (_CHECK_ISSUES.get(key) or _DEFAULT_ADVICE.get(key)
                                      or (label, "medium", None, None))
            out.append(Finding(
                key=f"check:{key}", title=title, devices=failing, risk=risk,
                effort="one_click" if fix else "manual", action_id=fix,
                advice=_REPORT_ADVICE.get(key) or note
                or "One click from Fleet Issues fixes it on every PC listed.",
            ))

        filling = [h for (h,) in (await self.session.execute(
            select(Device.hostname).join(AlertState, AlertState.device_id == Device.id)
            .where(AlertState.org_id == org_id, AlertState.check_key == "disk_forecast",
                   AlertState.state == "alerting").order_by(Device.hostname))).all()]
        if filling:
            out.append(Finding(
                key="disk_forecast", title="Disks forecast to fill within a week",
                devices=filling, risk="high", effort="one_click", action_id="clear_system_temp",
                advice="Clear temporary files now, before the disk fills and the PC stops working. "
                       "If it keeps filling, find what is growing.",
            ))

        today = date.today()
        for asset_id, name, ends in (await self.session.execute(
            select(Asset.id, Asset.name, Asset.warranty_expiry).where(
                Asset.org_id == org_id, Asset.archived_at.is_(None),
                Asset.warranty_expiry.is_not(None),
                Asset.warranty_expiry >= (today - timedelta(days=30)).isoformat(),
                Asset.warranty_expiry <= (today + timedelta(days=WARRANTY_DAYS)).isoformat(),
            ))).all():
            expired = ends < today.isoformat()
            out.append(Finding(
                key=f"warranty:{asset_id}",
                title=f"Warranty {'ended' if expired else 'ends'} {ends}: {name}",
                devices=[name], risk="medium" if expired else "low", effort="purchase",
                advice="Renew the warranty, or plan the replacement, before a repair falls on you.",
                per_device_work=False,
            ))

        cutoff = (today - timedelta(days=365 * OLD_PC_YEARS)).isoformat()
        purchases = {d: p for d, p in (await self.session.execute(
            select(Asset.device_id, Asset.purchase_date).where(
                Asset.org_id == org_id, Asset.device_id.is_not(None),
                Asset.purchase_date.is_not(None)))).all()}
        old = []
        for dev_id, host, bios in (await self.session.execute(
                select(Device.id, Device.hostname, Device.bios_release_date)
                .where(Device.org_id == org_id, Device.is_active.is_(True)))).all():
            when = purchases.get(dev_id) or bios
            if when and when <= cutoff:
                old.append(f"{host} ({when[:4]})")
        if old:
            out.append(Finding(
                key="old_hardware", title=f"PCs older than {OLD_PC_YEARS} years",
                devices=sorted(old), risk="low", effort="purchase",
                advice="Budget their replacement: older PCs fail more and slow people down.",
                per_device_work=False,
            ))
        return out

    async def refresh(self, org_id: uuid.UUID) -> None:
        settings = await SettingsService(self.session).ensure(org_id)
        findings = {f.key: f for f in await self._findings(org_id)}
        existing = {r.key: r for r in (await self.session.execute(
            select(Recommendation).where(Recommendation.org_id == org_id))).scalars()}
        now = utcnow()
        for key, f in findings.items():
            rec = existing.get(key)
            if rec is None:
                rec = Recommendation(org_id=org_id, key=key, status="open")
                self.session.add(rec)
            elif rec.status == "resolved":
                rec.status, rec.resolved_at = "open", None   # it came back
            rec.title = f.title[:200]
            rec.evidence = {"count": len(f.devices), "devices": f.devices[:25], "detail": f.detail}
            rec.risk, rec.effort, rec.action_id = f.risk, f.effort, f.action_id
            rec.advice = f.advice[:600]
            rec.time_minutes = len(f.devices) * settings.minutes_per_fix if f.per_device_work else None
        for key, rec in existing.items():
            if key not in findings and rec.status != "resolved":
                # Cleared. A dismissal ends with it, so a later recurrence is shown afresh.
                rec.status, rec.resolved_at = "resolved", now
                rec.dismissed_reason = rec.dismissed_at = rec.dismissed_by_user_id = None
        await self.session.commit()

    async def list(self, *, actor: User, status: str = "open") -> tuple[list[Recommendation], int | None]:
        await self.refresh(actor.org_id)
        rows = list((await self.session.execute(
            select(Recommendation).where(Recommendation.org_id == actor.org_id,
                                         Recommendation.status == status))).scalars())
        rows.sort(key=lambda r: (_RISK_RANK.get(r.risk, 1), -(r.evidence or {}).get("count", 0), r.title))
        cost = (await SettingsService(self.session).ensure(actor.org_id)).it_hourly_cost
        return rows, cost

    async def dismiss(self, *, actor: User, rec_id: uuid.UUID, reason: str) -> Recommendation:
        rec = await self._own(actor, rec_id)
        if rec.status != "open":
            raise ConflictError("Only an open recommendation can be dismissed.")
        rec.status, rec.dismissed_reason = "dismissed", reason[:300]
        rec.dismissed_by_user_id, rec.dismissed_at = actor.id, utcnow()
        await AuditService(self.session).record(
            org_id=actor.org_id, actor_id=actor.id, action="recommendation.dismiss",
            target_type="recommendation", target_id=str(rec.id),
            detail={"key": rec.key, "title": rec.title, "reason": rec.dismissed_reason},
        )
        await self.session.commit()
        return rec

    async def restore(self, *, actor: User, rec_id: uuid.UUID) -> Recommendation:
        rec = await self._own(actor, rec_id)
        if rec.status != "dismissed":
            raise ConflictError("Only a dismissed recommendation can be restored.")
        await AuditService(self.session).record(
            org_id=actor.org_id, actor_id=actor.id, action="recommendation.restore",
            target_type="recommendation", target_id=str(rec.id),
            detail={"key": rec.key, "was_dismissed_for": rec.dismissed_reason},
        )
        rec.status = "open"
        rec.dismissed_reason = rec.dismissed_at = rec.dismissed_by_user_id = None
        await self.session.commit()
        return rec

    async def _own(self, actor: User, rec_id: uuid.UUID) -> Recommendation:
        rec = await self.session.get(Recommendation, rec_id)
        if rec is None or rec.org_id != actor.org_id:
            raise NotFoundError("Recommendation not found")
        return rec
