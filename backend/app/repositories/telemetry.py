import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import as_utc, utcnow
from app.models.telemetry import (
    UPDATE_INSTALLED,
    DeviceEventLog,
    DeviceInstalledApp,
    DeviceService,
    DeviceWindowsUpdate,
    TelemetryDailyRollup,
    TelemetrySnapshot,
)


def _min_free_pct(disks: list[dict[str, Any]] | None) -> float | None:
    """Smallest free-space percentage across a snapshot's disks, or None if unknown."""
    pcts: list[float] = []
    for d in disks or []:
        total = d.get("total_gb") or 0
        free = d.get("free_gb")
        if total and free is not None:
            pcts.append(free / total * 100)
    return min(pcts) if pcts else None


class TelemetryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Snapshots ──────────────────────────────────────────────────────────

    async def add_snapshot(self, snapshot: TelemetrySnapshot) -> TelemetrySnapshot:
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot

    async def get_snapshots(
        self, device_id: uuid.UUID, since: datetime | None = None, limit: int = 100
    ) -> list[TelemetrySnapshot]:
        stmt = select(TelemetrySnapshot).where(TelemetrySnapshot.device_id == device_id)
        if since:
            stmt = stmt.where(TelemetrySnapshot.collected_at >= since)
        stmt = stmt.order_by(TelemetrySnapshot.collected_at.desc()).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def roll_up_snapshot(self, snapshot: TelemetrySnapshot) -> None:
        """Fold one snapshot into its device's daily rollup (running average + maxima).

        Called on every ingest so history survives the pruning below. Uses a running mean
        rather than re-aggregating the raw rows, which keeps this O(1) and correct even
        after the raw snapshots for that day are gone.
        """
        day = as_utc(snapshot.collected_at).date()
        row = (await self.session.execute(
            select(TelemetryDailyRollup).where(
                TelemetryDailyRollup.device_id == snapshot.device_id,
                TelemetryDailyRollup.day == day,
            )
        )).scalar_one_or_none()

        free_pct = _min_free_pct(snapshot.disks)
        if row is None:
            self.session.add(TelemetryDailyRollup(
                device_id=snapshot.device_id, org_id=snapshot.org_id, day=day, samples=1,
                cpu_avg=snapshot.cpu_percent, cpu_max=snapshot.cpu_percent,
                ram_used_avg_mb=snapshot.ram_used_mb, ram_used_max_mb=snapshot.ram_used_mb,
                disk_free_min_pct=free_pct,
            ))
        else:
            n = row.samples
            row.cpu_avg = (row.cpu_avg * n + snapshot.cpu_percent) / (n + 1)
            row.ram_used_avg_mb = int((row.ram_used_avg_mb * n + snapshot.ram_used_mb) / (n + 1))
            row.cpu_max = max(row.cpu_max, snapshot.cpu_percent)
            row.ram_used_max_mb = max(row.ram_used_max_mb, snapshot.ram_used_mb)
            if free_pct is not None:
                row.disk_free_min_pct = (
                    free_pct if row.disk_free_min_pct is None
                    else min(row.disk_free_min_pct, free_pct)
                )
            row.samples = n + 1
        await self.session.flush()

    async def prune_snapshots(
        self, device_id: uuid.UUID, *, keep_days: int, keep_min_rows: int = 60
    ) -> int:
        """Delete this device's raw snapshots older than `keep_days`, but ALWAYS keep its
        newest `keep_min_rows` whatever their age.

        Scoped to one device so the work stays proportional to the device that just
        reported — no cron, no fleet-wide sweep. Safe because nothing reads snapshots
        beyond "the latest" or "the last 60"; long-range history lives in the rollups.

        The floor matters: a device that was offline for weeks flushes its offline queue
        with old `collected_at` values. Pruning purely by age would delete all of them the
        moment they arrived, leaving the device with no snapshot at all — so it would show
        as "no telemetry yet" and its disk compliance check would go unknown.
        """
        if keep_days <= 0:
            return 0
        cutoff = utcnow() - timedelta(days=keep_days)
        newest = (
            select(TelemetrySnapshot.id)
            .where(TelemetrySnapshot.device_id == device_id)
            .order_by(TelemetrySnapshot.collected_at.desc())
            .limit(keep_min_rows)
            .subquery()
        )
        result = await self.session.execute(
            delete(TelemetrySnapshot).where(
                TelemetrySnapshot.device_id == device_id,
                TelemetrySnapshot.collected_at < cutoff,
                TelemetrySnapshot.id.not_in(select(newest.c.id)),
            )
        )
        return result.rowcount or 0

    async def get_rollups(
        self, device_id: uuid.UUID, limit: int = 90
    ) -> list[TelemetryDailyRollup]:
        result = await self.session.execute(
            select(TelemetryDailyRollup)
            .where(TelemetryDailyRollup.device_id == device_id)
            .order_by(TelemetryDailyRollup.day.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_latest_snapshot(self, device_id: uuid.UUID) -> TelemetrySnapshot | None:
        result = await self.session.execute(
            select(TelemetrySnapshot)
            .where(TelemetrySnapshot.device_id == device_id)
            .order_by(TelemetrySnapshot.collected_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    # ── Event logs ─────────────────────────────────────────────────────────

    async def replace_event_logs(
        self, device_id: uuid.UUID, entries: list[DeviceEventLog]
    ) -> None:
        await self.session.execute(
            delete(DeviceEventLog).where(DeviceEventLog.device_id == device_id)
        )
        self.session.add_all(entries)
        await self.session.flush()

    async def get_event_logs(
        self, device_id: uuid.UUID, limit: int = 200
    ) -> list[DeviceEventLog]:
        result = await self.session.execute(
            select(DeviceEventLog)
            .where(DeviceEventLog.device_id == device_id)
            .order_by(DeviceEventLog.occurred_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_critical_events_for_org(self, org_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count()).where(
                DeviceEventLog.org_id == org_id,
                DeviceEventLog.level == "Error",
            )
        )
        return result.scalar_one()

    # ── Installed apps ─────────────────────────────────────────────────────

    async def replace_installed_apps(
        self, device_id: uuid.UUID, entries: list[DeviceInstalledApp]
    ) -> None:
        await self.session.execute(
            delete(DeviceInstalledApp).where(DeviceInstalledApp.device_id == device_id)
        )
        self.session.add_all(entries)
        await self.session.flush()

    async def get_installed_apps(self, device_id: uuid.UUID) -> list[DeviceInstalledApp]:
        result = await self.session.execute(
            select(DeviceInstalledApp)
            .where(DeviceInstalledApp.device_id == device_id)
            .order_by(DeviceInstalledApp.name)
        )
        return list(result.scalars().all())

    async def count_apps_for_device(self, device_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count()).where(DeviceInstalledApp.device_id == device_id)
        )
        return result.scalar_one()

    async def count_apps_by_device_for_org(self, org_id: uuid.UUID) -> dict[uuid.UUID, int]:
        result = await self.session.execute(
            select(DeviceInstalledApp.device_id, func.count())
            .where(DeviceInstalledApp.org_id == org_id)
            .group_by(DeviceInstalledApp.device_id)
        )
        return {row[0]: row[1] for row in result.all()}

    # ── Services ───────────────────────────────────────────────────────────

    async def replace_services(
        self, device_id: uuid.UUID, entries: list[DeviceService]
    ) -> None:
        await self.session.execute(
            delete(DeviceService).where(DeviceService.device_id == device_id)
        )
        self.session.add_all(entries)
        await self.session.flush()

    async def get_services(self, device_id: uuid.UUID) -> list[DeviceService]:
        result = await self.session.execute(
            select(DeviceService)
            .where(DeviceService.device_id == device_id)
            .order_by(DeviceService.display_name)
        )
        return list(result.scalars().all())

    # ── Windows updates ────────────────────────────────────────────────────

    async def replace_windows_updates(
        self, device_id: uuid.UUID, entries: list[DeviceWindowsUpdate]
    ) -> None:
        await self.session.execute(
            delete(DeviceWindowsUpdate).where(DeviceWindowsUpdate.device_id == device_id)
        )
        self.session.add_all(entries)
        await self.session.flush()

    async def get_windows_updates(self, device_id: uuid.UUID) -> list[DeviceWindowsUpdate]:
        result = await self.session.execute(
            select(DeviceWindowsUpdate)
            .where(DeviceWindowsUpdate.device_id == device_id)
            .order_by(DeviceWindowsUpdate.title)
        )
        return list(result.scalars().all())

    async def count_pending_updates_for_org(self, org_id: uuid.UUID) -> int:
        """Updates not yet in effect anywhere in the org — the dashboard's headline number.

        Deliberately state-based rather than `is_installed == False`. is_installed means the
        update is on disk, which is true of one awaiting a restart, so the old predicate now
        quietly excludes exactly the updates a patch dashboard most needs to show: installed,
        not applied, and one reboot away.
        """
        result = await self.session.execute(
            select(func.count()).where(
                DeviceWindowsUpdate.org_id == org_id,
                DeviceWindowsUpdate.state != UPDATE_INSTALLED,
            )
        )
        return result.scalar_one()
