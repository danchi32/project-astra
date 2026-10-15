"""Workforce Insights ("Tracker") — aggregation and portal reads.

Aggregation mirrors telemetry's roll-up exactly: raw `activity_samples` are folded into
durable derived rows on ingest, per device, per day — never a cron, never a fleet sweep, so
the work stays proportional to the device that just reported. A day is RECOMPUTED from its
raw samples each time (idempotent), rather than nudged incrementally, because a projection
that is rebuilt cannot drift from the events it projects, and the raw window is short.

Phase 1 fills attendance: first-in, last-out and worked minutes, where "worked" means signed
in and not locked. That is honestly all transition events can establish — a machine left
unlocked counts as worked until P2's idle detection lands. The active/idle (P2) and
productive (P3) columns are left NULL here, not zeroed, so they read as "not measured yet".
"""
import uuid
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Device, Organization, User
from app.models.base import as_utc, utcnow
from app.models.workforce import (
    ACTIVITY_AWAY,
    ACTIVITY_PRESENT,
    SPAN_WORK,
    DailyUserSummary,
    WorkSession,
)
from app.repositories.workforce import WorkforceRepository, day_bounds
from app.schemas.telemetry import ActivityEvent
from app.schemas.workforce import DailyUserSummaryRead, WorkSessionRead
from app.services.entitlements import WORKFORCE_INSIGHTS, features_for
from app.services.exceptions import NotFoundError


@dataclass
class _Span:
    started_at: datetime
    ended_at: datetime | None   # None => still open (someone present right now, today)


def build_work_spans(
    events: list[tuple[str, datetime]],
    *,
    day: date,
    now: datetime,
    seed_present: bool,
) -> list[_Span]:
    """Turn one account's ordered presence events for one day into work spans.

    Pure and DB-free, so the span logic is unit-testable without a database. `events` are
    (kind, occurred_at) in ascending time, already scoped to `day`. `seed_present` carries
    whether the account was present at 00:00 (its last transition before the day was a
    PRESENT one) — the cross-midnight case.
    """
    day_start, day_end = day_bounds(day)
    is_today = day == now.astimezone(day_start.tzinfo).date()

    spans: list[_Span] = []
    open_at: datetime | None = day_start if seed_present else None
    last_ts: datetime | None = None

    for kind, ts in events:
        ts = max(day_start, min(ts, day_end))   # guard: clamp into the day
        last_ts = ts
        if kind in ACTIVITY_PRESENT:
            if open_at is None:
                open_at = ts
        elif kind in ACTIVITY_AWAY:
            if open_at is not None:
                if ts > open_at:
                    spans.append(_Span(open_at, ts))
                open_at = None

    if open_at is not None:
        if is_today:
            # Still signed in now — leave it open; worked is counted up to `now` below.
            spans.append(_Span(open_at, None))
        else:
            # A past day whose closing event we never saw (crash, hard power-off). Close at
            # the last signal we have that day; if the only event was the open itself, the
            # span is zero-length and dropped. When there were NO events at all (present at
            # 00:00 and nothing happened — continuous presence across a whole day), close at
            # the day's end. Conservative on purpose: an attendance product must not invent
            # hours it did not observe.
            end = day_end if last_ts is None else last_ts
            if end > open_at:
                spans.append(_Span(open_at, end))

    return spans


def _summarize(
    spans: list[_Span], *, day: date, now: datetime
) -> tuple[datetime, datetime | None, int] | None:
    """(first_in, last_out, worked_minutes) for a day's spans, or None if there was no
    presence. last_out is None while a span is still open (the person is in right now)."""
    if not spans:
        return None
    _, day_end = day_bounds(day)
    first_in = min(s.started_at for s in spans)
    worked_seconds = 0.0
    ongoing = False
    last_end: datetime | None = None
    for s in spans:
        end = s.ended_at
        if end is None:
            ongoing = True
            end = min(now, day_end)
        else:
            last_end = end if last_end is None else max(last_end, end)
        worked_seconds += max(0.0, (end - s.started_at).total_seconds())
    last_out = None if ongoing else last_end
    return first_in, last_out, int(round(worked_seconds / 60))


class WorkforceAggregator:
    """Ingest-side: store raw events and recompute the days they touch."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = WorkforceRepository(session)

    @staticmethod
    async def enabled_for(session: AsyncSession, org_id: uuid.UUID) -> bool:
        """Whether this org holds the workforce_insights entitlement. A lookup miss is
        treated as OFF — the opposite of the remediation/remote-control default — because
        this is monitoring data: the safe failure is to NOT collect, never to collect by
        accident."""
        org = await session.get(Organization, org_id)
        if org is None:
            return False
        return WORKFORCE_INSIGHTS in features_for(org.plan, org.entitlement_overrides)

    async def ingest_events(self, *, device: Device, events: list[ActivityEvent]) -> None:
        from app.models.workforce import ActivitySample

        now = utcnow()
        self.session.add_all([
            ActivitySample(
                device_id=device.id,
                org_id=device.org_id,
                username=e.username,
                kind=e.kind,
                session_id=e.session_id,
                occurred_at=e.occurred_at,
            )
            for e in events
        ])
        await self.session.flush()

        # Recompute every UTC day the batch touches — usually just today, but a device
        # flushing an offline queue can carry several.
        days = {as_utc(e.occurred_at).date() for e in events}
        for day in days:
            await self.recompute_day(device=device, day=day, now=now)

        await self.repo.prune_samples(
            device.id, keep_days=get_settings().workforce_activity_retention_days
        )

    async def recompute_day(self, *, device: Device, day: date, now: datetime) -> None:
        samples = await self.repo.get_samples_for_day(device.id, day)
        by_user: dict[str, list[tuple[str, datetime]]] = {}
        for s in samples:
            by_user.setdefault(s.username, []).append((s.kind, as_utc(s.occurred_at)))

        all_spans: list[WorkSession] = []
        for username, events in by_user.items():
            seed = await self.repo.was_present_at_day_start(device.id, username, day)
            spans = build_work_spans(events, day=day, now=now, seed_present=seed)
            for sp in spans:
                all_spans.append(WorkSession(
                    device_id=device.id,
                    org_id=device.org_id,
                    username=username,
                    day=day,
                    kind=SPAN_WORK,
                    started_at=sp.started_at,
                    ended_at=sp.ended_at,
                ))
            await self._write_summary(
                device=device, username=username, day=day,
                summary=_summarize(spans, day=day, now=now),
            )

        await self.repo.replace_work_sessions(device.id, day, all_spans)

    async def _write_summary(
        self,
        *,
        device: Device,
        username: str,
        day: date,
        summary: tuple[datetime, datetime | None, int] | None,
    ) -> None:
        existing = await self.repo.get_summary(device.id, username, day)
        if summary is None:
            # No presence left for this account/day (e.g. a correction removed it).
            if existing is not None:
                await self.session.delete(existing)
            return
        first_in, last_out, worked = summary
        if existing is None:
            self.session.add(DailyUserSummary(
                device_id=device.id,
                org_id=device.org_id,
                username=username,
                day=day,
                first_in=first_in,
                last_out=last_out,
                worked_minutes=worked,
            ))
        else:
            existing.first_in = first_in
            existing.last_out = last_out
            existing.worked_minutes = worked
        await self.session.flush()


class WorkforceService:
    """Portal-side reads. Org-scoped; the router gates on the entitlement and staff role."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = WorkforceRepository(session)

    async def attendance(
        self,
        *,
        actor: User,
        day_from: date,
        day_to: date,
        device_id: uuid.UUID | None = None,
        username: str | None = None,
    ) -> list[DailyUserSummaryRead]:
        rows = await self.repo.list_summaries(
            actor.org_id, day_from=day_from, day_to=day_to,
            device_id=device_id, username=username,
        )
        hostnames = await self.repo.hostnames_for({r.device_id for r in rows})
        out: list[DailyUserSummaryRead] = []
        for r in rows:
            read = DailyUserSummaryRead.model_validate(r)
            read.device_hostname = hostnames.get(r.device_id)
            out.append(read)
        return out

    async def day_sessions(
        self,
        *,
        actor: User,
        device_id: uuid.UUID,
        username: str,
        day: date,
    ) -> list[WorkSessionRead]:
        # Scoped to the actor's org in the query itself, so a device id from another org
        # returns nothing rather than leaking spans.
        device = await self.session.get(Device, device_id)
        if device is None or device.org_id != actor.org_id:
            raise NotFoundError("Device not found")
        rows = await self.repo.get_work_sessions(actor.org_id, device_id, username, day)
        return [WorkSessionRead.model_validate(r) for r in rows]
