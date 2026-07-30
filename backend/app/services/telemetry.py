import hashlib
import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, User
from app.models.telemetry import (
    DeviceEventLog,
    DeviceInstalledApp,
    DeviceService,
    DeviceWindowsUpdate,
    TelemetrySnapshot,
)
from app.core.config import get_settings
from app.repositories.devices import DeviceRepository
from app.repositories.telemetry import TelemetryRepository
from app.schemas.telemetry import DashboardSummary, TelemetryPush
from app.schemas.devices import ONLINE_THRESHOLD
from app.models.base import as_utc, utcnow
from app.services.exceptions import NotFoundError


def _fingerprint(items: Sequence[Any], fields: tuple[str, ...]) -> str:
    """Stable digest of an inventory collection, over `fields` only.

    Sorted, so the agent reporting the same set in a different order still counts as
    unchanged — otherwise the skip would almost never fire. `collected_at` is deliberately
    excluded: it changes on every push by definition and would defeat the whole thing.
    """
    rows = sorted(
        "\x1f".join("" if (v := getattr(i, f, None)) is None else str(v) for f in fields)
        for i in items
    )
    return hashlib.sha256("\x1e".join(rows).encode("utf-8")).hexdigest()


class TelemetryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = TelemetryRepository(session)
        self.devices = DeviceRepository(session)

    async def ingest(self, *, device: Device, data: TelemetryPush) -> None:
        now = data.collected_at

        if data.hardware is not None:
            hw = data.hardware
            if hw.manufacturer is not None:
                device.manufacturer = hw.manufacturer
            if hw.model is not None:
                device.model = hw.model
            if hw.cpu_name is not None:
                device.cpu_name = hw.cpu_name
            if hw.total_ram_mb is not None:
                device.total_ram_mb = hw.total_ram_mb
            if hw.total_storage_gb is not None:
                device.total_storage_gb = hw.total_storage_gb

        snapshot = await self.repo.add_snapshot(
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
        # Fold into the day's rollup first, THEN prune — so history is captured before
        # any raw row is dropped. Both are scoped to this device, so the work per ingest
        # stays constant no matter how large the fleet gets.
        await self.repo.roll_up_snapshot(snapshot)
        settings = get_settings()
        await self.repo.prune_snapshots(
            device.id,
            keep_days=settings.telemetry_retention_days,
            keep_min_rows=settings.telemetry_keep_min_snapshots,
        )

        # Inventory collections are re-sent in full every hour. Rewriting one that hasn't
        # changed is pure churn (see Device.*_hash), so each is fingerprinted and skipped
        # when identical — which also avoids building the ORM objects at all.
        if data.event_logs:
            digest = _fingerprint(
                data.event_logs, ("log_name", "source", "event_id", "level", "message", "occurred_at")
            )
            if digest != device.events_hash:
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
                device.events_hash = digest

        if data.installed_apps:
            digest = _fingerprint(
                data.installed_apps, ("name", "version", "publisher", "install_date")
            )
            if digest != device.apps_hash:
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
                device.apps_hash = digest

        if data.services:
            digest = _fingerprint(
                data.services, ("name", "display_name", "status", "start_type")
            )
            if digest != device.services_hash:
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
                device.services_hash = digest

        if data.windows_updates:
            # state, not is_installed: an update moving pending -> pending_restart, or
            # failing with a new error code, is a change worth writing. Fingerprinting the
            # boolean would treat "installed, needs a reboot" as identical to "not installed"
            # and skip the write, so the portal would keep showing the older, wronger row.
            digest = _fingerprint(
                data.windows_updates,
                # resolved_state, not the raw state field: an older agent leaves state None
                # on every push, so fingerprinting it would make every collection look
                # unchanged and the write would be skipped forever.
                ("kb_article_id", "title", "resolved_state", "error_code", "installed_on"),
            )
            if digest != device.updates_hash:
                await self.repo.replace_windows_updates(
                    device.id,
                    [
                        DeviceWindowsUpdate(
                            device_id=device.id,
                            org_id=device.org_id,
                            kb_article_id=u.kb_article_id,
                            title=u.title,
                            state=u.resolved_state,
                            error_code=u.error_code,
                            installed_on=u.installed_on,
                            collected_at=now,
                        )
                        for u in data.windows_updates
                    ],
                )
                device.updates_hash = digest

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
