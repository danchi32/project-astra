import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.workforce import (
    ACTIVITY_FOREGROUND,
    ActivitySample,
    DailyAppUsage,
    DailyUserSummary,
    WorkSession,
)


def day_bounds(day: date) -> tuple[datetime, datetime]:
    """[00:00, next 00:00) in UTC for a calendar day. Attendance is computed in UTC in P1;
    a per-org/team shift timezone is a configuration item for a later phase."""
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


class WorkforceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Raw samples (ingest side) ────────────────────────────────────────────

    async def add_samples(self, samples: list[ActivitySample]) -> None:
        self.session.add_all(samples)
        await self.session.flush()

    async def presence_samples_for_day(
        self, device_id: uuid.UUID, day: date
    ) -> list[ActivitySample]:
        """The day's session/presence events only (logon/logoff/lock/unlock/active/idle),
        ordered. These are few — a handful of transitions — and drive the attendance spans."""
        start, end = day_bounds(day)
        result = await self.session.execute(
            select(ActivitySample)
            .where(
                ActivitySample.device_id == device_id,
                ActivitySample.occurred_at >= start,
                ActivitySample.occurred_at < end,
                ActivitySample.kind != ACTIVITY_FOREGROUND,
            )
            .order_by(ActivitySample.occurred_at.asc())
        )
        return list(result.scalars().all())

    async def foreground_counts_for_day(
        self, device_id: uuid.UUID, day: date
    ) -> list[tuple[str, str | None, str | None, str | None, bool, bool, int]]:
        """Foreground samples rolled up in the database to one row per distinct
        (username, app, domain, path, idle, idle_suspect) with its count — productivity is
        counts, so grouping in SQL avoids pulling a whole day of ~30s samples into Python on
        every push. Returns (username, app, domain, path, idle, idle_suspect, count)."""
        start, end = day_bounds(day)
        result = await self.session.execute(
            select(
                ActivitySample.username,
                ActivitySample.app,
                ActivitySample.domain,
                ActivitySample.path,
                ActivitySample.idle,
                ActivitySample.idle_suspect,
                func.count(),
            )
            .where(
                ActivitySample.device_id == device_id,
                ActivitySample.occurred_at >= start,
                ActivitySample.occurred_at < end,
                ActivitySample.kind == ACTIVITY_FOREGROUND,
            )
            .group_by(
                ActivitySample.username,
                ActivitySample.app,
                ActivitySample.domain,
                ActivitySample.path,
                ActivitySample.idle,
                ActivitySample.idle_suspect,
            )
        )
        return [(r[0], r[1], r[2], r[3], r[4], r[5], r[6]) for r in result.all()]

    async def was_present_at_day_start(
        self, device_id: uuid.UUID, username: str, day: date
    ) -> bool:
        """Whether this account's last transition BEFORE the day left it present.

        This is the cross-midnight seed: someone who logged on at 23:00 and is still signed
        in at 00:00 was present from the start of the new day, and the day's worked time has
        to begin at 00:00, not at their first event of the day (there may be none)."""
        from app.models.workforce import ACTIVITY_FOREGROUND, ACTIVITY_PRESENT

        start, _ = day_bounds(day)
        result = await self.session.execute(
            select(ActivitySample.kind)
            .where(
                ActivitySample.device_id == device_id,
                ActivitySample.username == username,
                ActivitySample.occurred_at < start,
                # Presence events only. Foreground (productivity) samples fire every ~30s, so
                # without this the "last sample before midnight" is almost always a foreground
                # row — never a presence kind — and the seed would wrongly read as "away",
                # dropping a night-shift user's worked time after midnight.
                ActivitySample.kind != ACTIVITY_FOREGROUND,
            )
            .order_by(ActivitySample.occurred_at.desc())
            .limit(1)
        )
        kind = result.scalar_one_or_none()
        return kind in ACTIVITY_PRESENT

    async def usernames_for_day(self, device_id: uuid.UUID, day: date) -> list[str]:
        start, end = day_bounds(day)
        result = await self.session.execute(
            select(ActivitySample.username)
            .where(
                ActivitySample.device_id == device_id,
                ActivitySample.occurred_at >= start,
                ActivitySample.occurred_at < end,
            )
            .distinct()
        )
        return list(result.scalars().all())

    async def prune_samples(self, device_id: uuid.UUID, *, keep_days: int) -> int:
        """Drop this device's raw samples older than the retention window, on ingest.

        Scoped to the device that just reported — no fleet sweep, no cron — exactly like
        telemetry snapshot pruning. The derived work_sessions / daily_user_summary are the
        durable record and are never pruned, so history survives this."""
        if keep_days <= 0:
            return 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
        result = await self.session.execute(
            delete(ActivitySample).where(
                ActivitySample.device_id == device_id,
                ActivitySample.occurred_at < cutoff,
            )
        )
        return result.rowcount or 0

    # ── Derived rows (aggregation side) ───────────────────────────────────────

    async def replace_work_sessions(
        self, device_id: uuid.UUID, day: date, spans: list[WorkSession]
    ) -> None:
        """Swap one (device, day)'s spans for the freshly recomputed set.

        Delete-then-insert, because the spans are a projection of the raw samples for that
        day: recomputing has to be able to REMOVE a span that no longer exists (a corrected
        event), not only add. Scoped to the one day so other days are untouched."""
        await self.session.execute(
            delete(WorkSession).where(
                WorkSession.device_id == device_id, WorkSession.day == day
            )
        )
        self.session.add_all(spans)
        await self.session.flush()

    async def replace_app_usage(
        self, device_id: uuid.UUID, day: date, rows: list[DailyAppUsage]
    ) -> None:
        """Swap one (device, day)'s per-app rows for the freshly recomputed set — a
        projection of the day's foreground samples, same discipline as work_sessions."""
        await self.session.execute(
            delete(DailyAppUsage).where(
                DailyAppUsage.device_id == device_id, DailyAppUsage.day == day
            )
        )
        self.session.add_all(rows)
        await self.session.flush()

    async def app_usage_for_user(
        self, org_id: uuid.UUID, username: str, *, day_from: date, day_to: date
    ) -> list[DailyAppUsage]:
        result = await self.session.execute(
            select(DailyAppUsage).where(
                DailyAppUsage.org_id == org_id,
                DailyAppUsage.username == username,
                DailyAppUsage.day >= day_from,
                DailyAppUsage.day <= day_to,
            )
        )
        return list(result.scalars().all())

    async def get_summary(
        self, device_id: uuid.UUID, username: str, day: date
    ) -> DailyUserSummary | None:
        result = await self.session.execute(
            select(DailyUserSummary).where(
                DailyUserSummary.device_id == device_id,
                DailyUserSummary.username == username,
                DailyUserSummary.day == day,
            )
        )
        return result.scalar_one_or_none()

    # ── Portal reads ──────────────────────────────────────────────────────────

    async def list_summaries(
        self,
        org_id: uuid.UUID,
        *,
        day_from: date,
        day_to: date,
        device_id: uuid.UUID | None = None,
        username: str | None = None,
    ) -> list[DailyUserSummary]:
        stmt = select(DailyUserSummary).where(
            DailyUserSummary.org_id == org_id,
            DailyUserSummary.day >= day_from,
            DailyUserSummary.day <= day_to,
        )
        if device_id is not None:
            stmt = stmt.where(DailyUserSummary.device_id == device_id)
        if username is not None:
            stmt = stmt.where(DailyUserSummary.username == username)
        stmt = stmt.order_by(
            DailyUserSummary.day.desc(),
            DailyUserSummary.username.asc(),
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_work_sessions(
        self, org_id: uuid.UUID, device_id: uuid.UUID, username: str, day: date
    ) -> list[WorkSession]:
        result = await self.session.execute(
            select(WorkSession)
            .where(
                WorkSession.org_id == org_id,
                WorkSession.device_id == device_id,
                WorkSession.username == username,
                WorkSession.day == day,
            )
            .order_by(WorkSession.started_at.asc())
        )
        return list(result.scalars().all())

    async def hostnames_for(
        self, device_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, str]:
        if not device_ids:
            return {}
        result = await self.session.execute(
            select(Device.id, Device.hostname).where(Device.id.in_(device_ids))
        )
        return {row[0]: row[1] for row in result.all()}
