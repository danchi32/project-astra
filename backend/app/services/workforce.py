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
    ActivitySample,
    DailyAppUsage,
    DailyUserSummary,
    WorkSession,
)
from app.repositories.workforce import WorkforceRepository, day_bounds
from app.schemas.telemetry import ActivityEvent
from app.schemas.workforce import (
    AppUsageRead,
    DailyUserSummaryRead,
    UserDetailRead,
    WorkSessionRead,
)
from app.services.entitlements import WORKFORCE_INSIGHTS, features_for
from app.services.exceptions import NotFoundError
from app.services.workforce_categories import (
    NEUTRAL,
    PRIVATE_PLACEHOLDER,
    PRODUCTIVE,
    UNPRODUCTIVE,
    classify,
    is_sensitive,
)


@dataclass
class _Span:
    started_at: datetime
    ended_at: datetime | None   # None => still open (someone present right now, today)


@dataclass
class _Productivity:
    active_minutes: int
    idle_minutes: int
    productive_minutes: int
    neutral_minutes: int
    unproductive_minutes: int
    suspected_idle_minutes: int
    # (label, bucket, minutes) per app/site, biggest first.
    apps: list[tuple[str, str, int]]


# One foreground group from the DB roll-up: (app, domain, path, idle, idle_suspect, count).
_FgGroup = tuple[str | None, str | None, str | None, bool, bool, int]


def _productivity(groups: list[_FgGroup], *, sample_seconds: int) -> _Productivity | None:
    """Attribute foreground samples to active/idle time, productivity buckets and per-app totals.

    Sampling, not timing: each foreground sample stands for `sample_seconds` of time in that
    app (the agent's polling interval), so minutes = samples × seconds ÷ 60. Fed pre-grouped
    counts (one row per distinct app/site) from SQL, so this never iterates raw samples.

    Idle windows (no input past the threshold) count as idle time only — they are NOT attributed
    to a productivity bucket or an app total, because time a person is away from the keyboard is
    not time spent "in" that app. So active = productive + neutral + unproductive.
    """
    if not groups:
        return None

    bucket_counts: dict[str, int] = {PRODUCTIVE: 0, NEUTRAL: 0, UNPRODUCTIVE: 0}
    label_counts: dict[str, tuple[str, int]] = {}
    suspect = 0
    idle = 0
    for app, domain, path, is_idle, idle_suspect, count in groups:
        if is_idle:
            idle += count
            continue
        bucket, _label = classify(app, domain)
        bucket_counts[bucket] += count
        if idle_suspect:
            suspect += count
        # The display label is the domain, plus the path when one was captured (path mode).
        label = domain or app or "Other"
        if domain and path:
            label = f"{domain}{path}"
        prev_bucket, prev_n = label_counts.get(label, (bucket, 0))
        label_counts[label] = (prev_bucket, prev_n + count)

    def mins(n: int) -> int:
        return int(round(n * sample_seconds / 60))

    apps = sorted(
        ((label, b, mins(n)) for label, (b, n) in label_counts.items()),
        key=lambda t: t[2],
        reverse=True,
    )
    return _Productivity(
        active_minutes=mins(sum(bucket_counts.values())),
        idle_minutes=mins(idle),
        productive_minutes=mins(bucket_counts[PRODUCTIVE]),
        neutral_minutes=mins(bucket_counts[NEUTRAL]),
        unproductive_minutes=mins(bucket_counts[UNPRODUCTIVE]),
        suspected_idle_minutes=mins(suspect),
        apps=[a for a in apps if a[2] > 0],
    )


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
        now = utcnow()
        self.session.add_all([self._to_sample(device, e) for e in events])
        await self.session.flush()

        # Recompute every UTC day the batch touches — usually just today, but a device
        # flushing an offline queue can carry several.
        days = {as_utc(e.occurred_at).date() for e in events}
        for day in days:
            await self.recompute_day(device=device, day=day, now=now)

        await self.repo.prune_samples(
            device.id, keep_days=get_settings().workforce_activity_retention_days
        )

    @staticmethod
    def _to_sample(device: Device, e: ActivityEvent) -> ActivitySample:
        # Canonicalise the account key. Presence events come from the Service (the WTS token's
        # DOMAIN\user) and foreground samples from the Tray (Environment DOMAIN\user); Windows
        # account names are case-insensitive, so these can differ only in case. Lower-casing
        # both on ingest keeps one person's attendance and productivity on the same row rather
        # than splitting into two look-alike accounts.
        username = e.username.strip().lower()
        # Host only — strip any path an agent put in the domain field by mistake.
        domain = (e.domain.split("/")[0].strip().lower() or None) if e.domain else None
        # Path, with the query string and fragment removed — belt to the agent's braces, since
        # a stored query string is the one thing §6 never permits.
        path = None
        if e.path:
            p = e.path.split("?")[0].split("#")[0].strip()
            path = p or None
        # Banking / health / gov: the path alone is sensitive, so it is dropped and the site
        # is recorded as a placeholder, never its real domain.
        if is_sensitive(domain):
            domain, path = PRIVATE_PLACEHOLDER, None
        return ActivitySample(
            device_id=device.id,
            org_id=device.org_id,
            username=username,
            kind=e.kind,
            session_id=e.session_id,
            occurred_at=e.occurred_at,
            app=e.app,
            domain=domain,
            path=path,
            idle=e.idle,
            idle_suspect=e.idle_suspect,
        )

    async def recompute_day(self, *, device: Device, day: date, now: datetime) -> None:
        sample_seconds = get_settings().workforce_foreground_sample_seconds

        # Presence events (few) drive attendance spans; foreground samples (many, ~30s apart)
        # drive productivity and are rolled up to per-app counts in SQL rather than loaded row
        # by row. A user may have one, the other, or both.
        presence_by_user: dict[str, list[tuple[str, datetime]]] = {}
        for s in await self.repo.presence_samples_for_day(device.id, day):
            if s.kind in ACTIVITY_PRESENT or s.kind in ACTIVITY_AWAY:
                presence_by_user.setdefault(s.username, []).append((s.kind, as_utc(s.occurred_at)))

        fg_by_user: dict[str, list[_FgGroup]] = {}
        for username, app, domain, path, idle, suspect, count in (
            await self.repo.foreground_counts_for_day(device.id, day)
        ):
            fg_by_user.setdefault(username, []).append((app, domain, path, idle, suspect, count))

        all_spans: list[WorkSession] = []
        all_app_usage: list[DailyAppUsage] = []
        for username in set(presence_by_user) | set(fg_by_user):
            seed = await self.repo.was_present_at_day_start(device.id, username, day)
            spans = build_work_spans(
                presence_by_user.get(username, []), day=day, now=now, seed_present=seed)
            for sp in spans:
                all_spans.append(WorkSession(
                    device_id=device.id, org_id=device.org_id, username=username, day=day,
                    kind=SPAN_WORK, started_at=sp.started_at, ended_at=sp.ended_at,
                ))

            prod = _productivity(fg_by_user.get(username, []), sample_seconds=sample_seconds)
            await self._write_summary(
                device=device, username=username, day=day,
                attendance=_summarize(spans, day=day, now=now), prod=prod,
            )
            if prod is not None:
                all_app_usage.extend(
                    DailyAppUsage(
                        device_id=device.id, org_id=device.org_id, username=username, day=day,
                        label=label[:260], bucket=bucket, minutes=minutes,
                    )
                    for label, bucket, minutes in prod.apps
                )

        await self.repo.replace_work_sessions(device.id, day, all_spans)
        await self.repo.replace_app_usage(device.id, day, all_app_usage)

    async def _write_summary(
        self,
        *,
        device: Device,
        username: str,
        day: date,
        attendance: tuple[datetime, datetime | None, int] | None,
        prod: _Productivity | None,
    ) -> None:
        existing = await self.repo.get_summary(device.id, username, day)
        if attendance is None and prod is None:
            # Nothing left for this account/day (e.g. a correction removed it).
            if existing is not None:
                await self.session.delete(existing)
            return

        first_in, last_out, worked = attendance or (None, None, 0)
        # Productivity columns stay NULL when there is no foreground data, so the UI shows
        # "—" (not measured) rather than a misleading 0.
        active = prod.active_minutes if prod else None
        idle = prod.idle_minutes if prod else None
        productive = prod.productive_minutes if prod else None
        neutral = prod.neutral_minutes if prod else None
        unproductive = prod.unproductive_minutes if prod else None
        suspected_idle = prod.suspected_idle_minutes if prod else None

        if existing is None:
            self.session.add(DailyUserSummary(
                device_id=device.id, org_id=device.org_id, username=username, day=day,
                first_in=first_in, last_out=last_out, worked_minutes=worked,
                active_minutes=active, idle_minutes=idle, productive_minutes=productive,
                neutral_minutes=neutral, unproductive_minutes=unproductive,
                suspected_idle_minutes=suspected_idle,
            ))
        else:
            existing.first_in = first_in
            existing.last_out = last_out
            existing.worked_minutes = worked
            existing.active_minutes = active
            existing.idle_minutes = idle
            existing.productive_minutes = productive
            existing.neutral_minutes = neutral
            existing.unproductive_minutes = unproductive
            existing.suspected_idle_minutes = suspected_idle
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

    async def user_detail(
        self, *, actor: User, username: str, day_from: date, day_to: date
    ) -> UserDetailRead:
        rows = await self.repo.list_summaries(
            actor.org_id, day_from=day_from, day_to=day_to, username=username)
        hostnames = await self.repo.hostnames_for({r.device_id for r in rows})

        days: list[DailyUserSummaryRead] = []
        for r in rows:
            read = DailyUserSummaryRead.model_validate(r)
            read.device_hostname = hostnames.get(r.device_id)
            days.append(read)

        def total(attr: str) -> int | None:
            # Sum the measured days; None only when NONE of them measured it (so the UI can
            # tell "nobody tracked apps" from "tracked, and it was zero").
            vals = [getattr(r, attr) for r in rows if getattr(r, attr) is not None]
            return sum(vals) if vals else None

        # App/site breakdown, summed across days and devices by label.
        usage = await self.repo.app_usage_for_user(
            actor.org_id, username, day_from=day_from, day_to=day_to)
        merged: dict[str, tuple[str, int]] = {}
        for u in usage:
            bucket, mins = merged.get(u.label, (u.bucket, 0))
            merged[u.label] = (bucket, mins + u.minutes)
        apps = [
            AppUsageRead(label=label, bucket=bucket, minutes=mins)
            for label, (bucket, mins) in sorted(
                merged.items(), key=lambda kv: kv[1][1], reverse=True)
        ]

        return UserDetailRead(
            username=username,
            day_from=day_from,
            day_to=day_to,
            worked_minutes=sum(r.worked_minutes for r in rows),
            active_minutes=total("active_minutes"),
            idle_minutes=total("idle_minutes"),
            productive_minutes=total("productive_minutes"),
            neutral_minutes=total("neutral_minutes"),
            unproductive_minutes=total("unproductive_minutes"),
            suspected_idle_minutes=total("suspected_idle_minutes"),
            days=days,
            apps=apps,
        )

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
