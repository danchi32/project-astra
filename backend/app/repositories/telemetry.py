import uuid
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telemetry import (
    DeviceEventLog,
    DeviceInstalledApp,
    DeviceService,
    DeviceWindowsUpdate,
    TelemetrySnapshot,
)


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
        result = await self.session.execute(
            select(func.count()).where(
                DeviceWindowsUpdate.org_id == org_id,
                DeviceWindowsUpdate.is_installed == False,  # noqa: E712
            )
        )
        return result.scalar_one()
