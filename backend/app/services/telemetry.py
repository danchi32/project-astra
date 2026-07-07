import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, User
from app.models.telemetry import (
    DeviceEventLog,
    DeviceInstalledApp,
    DeviceService,
    DeviceWindowsUpdate,
    TelemetrySnapshot,
)
from app.repositories.devices import DeviceRepository
from app.repositories.telemetry import TelemetryRepository
from app.schemas.telemetry import DashboardSummary, TelemetryPush
from app.schemas.devices import ONLINE_THRESHOLD
from app.models.base import as_utc, utcnow
from app.services.exceptions import NotFoundError


class TelemetryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = TelemetryRepository(session)
        self.devices = DeviceRepository(session)

    async def ingest(self, *, device: Device, data: TelemetryPush) -> None:
        now = data.collected_at

        await self.repo.add_snapshot(
            TelemetrySnapshot(
                device_id=device.id,
                org_id=device.org_id,
                cpu_percent=data.cpu_percent,
                ram_total_mb=data.ram_total_mb,
                ram_used_mb=data.ram_used_mb,
                disks=[d.model_dump() for d in data.disks],
                collected_at=now,
            )
        )

        if data.event_logs:
            await self.repo.replace_event_logs(
                device.id,
                [
                    DeviceEventLog(
                        device_id=device.id,
                        org_id=device.org_id,
                        log_name=e.log_name,
                        source=e.source,
                        event_id=e.event_id,
                        level=e.level,
                        message=e.message[:2000],
                        occurred_at=e.occurred_at,
                    )
                    for e in data.event_logs
                ],
            )

        if data.installed_apps:
            await self.repo.replace_installed_apps(
                device.id,
                [
                    DeviceInstalledApp(
                        device_id=device.id,
                        org_id=device.org_id,
                        name=a.name,
                        version=a.version,
                        publisher=a.publisher,
                        install_date=a.install_date,
                        collected_at=now,
                    )
                    for a in data.installed_apps
                ],
            )

        if data.services:
            await self.repo.replace_services(
                device.id,
                [
                    DeviceService(
                        device_id=device.id,
                        org_id=device.org_id,
                        name=s.name,
                        display_name=s.display_name,
                        status=s.status,
                        start_type=s.start_type,
                        collected_at=now,
                    )
                    for s in data.services
                ],
            )

        if data.windows_updates:
            await self.repo.replace_windows_updates(
                device.id,
                [
                    DeviceWindowsUpdate(
                        device_id=device.id,
                        org_id=device.org_id,
                        kb_article_id=u.kb_article_id,
                        title=u.title,
                        is_installed=u.is_installed,
                        installed_on=u.installed_on,
                        collected_at=now,
                    )
                    for u in data.windows_updates
                ],
            )

        await self.session.commit()

    async def get_dashboard_summary(self, *, actor: User) -> DashboardSummary:
        org_devices = await self.devices.list_by_org(actor.org_id)
        now = utcnow()
        online = sum(
            1
            for d in org_devices
            if d.last_seen_at is not None
            and now - as_utc(d.last_seen_at) < ONLINE_THRESHOLD
        )
        total = len(org_devices)

        # Aggregate latest CPU/RAM across online devices
        cpu_vals: list[float] = []
        ram_pcts: list[float] = []
        for device in org_devices:
            snap = await self.repo.get_latest_snapshot(device.id)
            if snap:
                cpu_vals.append(snap.cpu_percent)
                if snap.ram_total_mb > 0:
                    ram_pcts.append(snap.ram_used_mb / snap.ram_total_mb * 100)

        avg_cpu = sum(cpu_vals) / len(cpu_vals) if cpu_vals else 0.0
        avg_ram = sum(ram_pcts) / len(ram_pcts) if ram_pcts else 0.0

        critical_events = await self.repo.count_critical_events_for_org(actor.org_id)
        pending_updates = await self.repo.count_pending_updates_for_org(actor.org_id)

        return DashboardSummary(
            total_devices=total,
            online_devices=online,
            offline_devices=total - online,
            avg_cpu_percent=round(avg_cpu, 1),
            avg_ram_percent=round(avg_ram, 1),
            critical_event_count=critical_events,
            pending_update_count=pending_updates,
        )

    async def get_snapshots(self, *, actor: User, device_id: uuid.UUID, limit: int = 60):
        await self._assert_owns(actor, device_id)
        return await self.repo.get_snapshots(device_id, limit=limit)

    async def get_event_logs(self, *, actor: User, device_id: uuid.UUID):
        await self._assert_owns(actor, device_id)
        return await self.repo.get_event_logs(device_id)

    async def get_installed_apps(self, *, actor: User, device_id: uuid.UUID):
        await self._assert_owns(actor, device_id)
        return await self.repo.get_installed_apps(device_id)

    async def get_services(self, *, actor: User, device_id: uuid.UUID):
        await self._assert_owns(actor, device_id)
        return await self.repo.get_services(device_id)

    async def get_windows_updates(self, *, actor: User, device_id: uuid.UUID):
        await self._assert_owns(actor, device_id)
        return await self.repo.get_windows_updates(device_id)

    async def _assert_owns(self, actor: User, device_id: uuid.UUID) -> None:
        device = await self.devices.get(device_id)
        if device is None or device.org_id != actor.org_id:
            raise NotFoundError("Device not found")
