from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RemediationStatus, User
from app.models.base import as_utc, utcnow
from app.repositories.devices import DeviceRepository
from app.repositories.remediation import RemediationRepository
from app.repositories.telemetry import TelemetryRepository
from app.schemas.devices import ONLINE_THRESHOLD
from app.schemas.report import (
    AssetReport,
    FleetHealthDeviceRow,
    FleetHealthReport,
    RemediationReport,
    RemediationReportRow,
)
from app.services.assets import AssetService


class ReportService:
    """Read-only aggregation over devices/telemetry/remediation/assets. Nothing here is
    persisted — reports are computed on demand from the existing operational data."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.devices = DeviceRepository(session)
        self.telemetry = TelemetryRepository(session)
        self.remediation = RemediationRepository(session)
        self.assets = AssetService(session)

    async def fleet_health(self, *, actor: User) -> FleetHealthReport:
        org_devices = await self.devices.list_by_org(actor.org_id)
        now = utcnow()

        rows: list[FleetHealthDeviceRow] = []
        cpu_vals: list[float] = []
        ram_pcts: list[float] = []
        online_count = 0
        total_critical = 0
        total_pending = 0

        for device in org_devices:
            online = (
                device.last_seen_at is not None
                and now - as_utc(device.last_seen_at) < ONLINE_THRESHOLD
            )
            if online:
                online_count += 1

            snap = await self.telemetry.get_latest_snapshot(device.id)
            cpu = snap.cpu_percent if snap else None
            ram = (
                snap.ram_used_mb / snap.ram_total_mb * 100
                if snap and snap.ram_total_mb
                else None
            )
            disk_free_min = None
            if snap and snap.disks:
                pcts = [
                    d["free_gb"] / d["total_gb"] * 100
                    for d in snap.disks
                    if d.get("total_gb")
                ]
                disk_free_min = round(min(pcts), 1) if pcts else None
            if cpu is not None:
                cpu_vals.append(cpu)
            if ram is not None:
                ram_pcts.append(ram)

            events = await self.telemetry.get_event_logs(device.id)
            critical = sum(1 for e in events if e.level == "Error")
            updates = await self.telemetry.get_windows_updates(device.id)
            pending = sum(1 for u in updates if not u.is_installed)
            total_critical += critical
            total_pending += pending

            rows.append(
                FleetHealthDeviceRow(
                    device_id=device.id,
                    hostname=device.hostname,
                    status="online" if online else "offline",
                    cpu_percent=round(cpu, 1) if cpu is not None else None,
                    ram_percent=round(ram, 1) if ram is not None else None,
                    disk_free_percent_min=disk_free_min,
                    critical_event_count=critical,
                    pending_update_count=pending,
                    last_seen_at=device.last_seen_at,
                )
            )

        return FleetHealthReport(
            generated_at=now,
            total_devices=len(org_devices),
            online_devices=online_count,
            offline_devices=len(org_devices) - online_count,
            avg_cpu_percent=round(sum(cpu_vals) / len(cpu_vals), 1) if cpu_vals else 0.0,
            avg_ram_percent=round(sum(ram_pcts) / len(ram_pcts), 1) if ram_pcts else 0.0,
            total_critical_events=total_critical,
            total_pending_updates=total_pending,
            devices=sorted(rows, key=lambda r: r.hostname),
        )

    async def remediation_report(self, *, actor: User, days: int = 30) -> RemediationReport:
        since = utcnow() - timedelta(days=days)
        tasks = await self.remediation.list_by_org(actor.org_id, limit=1000)
        tasks = [t for t in tasks if as_utc(t.created_at) >= since]
        device_hosts = {d.id: d.hostname for d in await self.devices.list_by_org(actor.org_id)}

        by_tier: dict[str, int] = {}
        by_action: dict[str, int] = {}
        succeeded = failed = pending = 0
        rows: list[RemediationReportRow] = []
        for t in tasks:
            by_tier[t.tier] = by_tier.get(t.tier, 0) + 1
            by_action[t.action_id] = by_action.get(t.action_id, 0) + 1
            if t.status == RemediationStatus.SUCCEEDED:
                succeeded += 1
            elif t.status == RemediationStatus.FAILED:
                failed += 1
            elif t.status == RemediationStatus.PENDING_APPROVAL:
                pending += 1
            rows.append(
                RemediationReportRow(
                    task_id=t.id,
                    device_hostname=device_hosts.get(t.device_id),
                    action_id=t.action_id,
                    tier=t.tier,
                    status=t.status.value,
                    source=t.source.value,
                    created_at=t.created_at,
                    completed_at=t.completed_at,
                )
            )

        resolved = succeeded + failed
        return RemediationReport(
            generated_at=utcnow(),
            period_days=days,
            total_tasks=len(tasks),
            succeeded=succeeded,
            failed=failed,
            pending_approval=pending,
            success_rate=round(succeeded / resolved * 100, 1) if resolved else 0.0,
            by_tier=by_tier,
            by_action=by_action,
            tasks=sorted(rows, key=lambda r: r.created_at, reverse=True),
        )

    async def asset_report(self, *, actor: User) -> AssetReport:
        summary = await self.assets.summary(org_id=actor.org_id)
        assets = await self.assets.list_for_org(org_id=actor.org_id)
        return AssetReport(generated_at=utcnow(), summary=summary, assets=assets)
