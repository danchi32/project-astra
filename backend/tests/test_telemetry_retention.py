"""Raw snapshots are pruned; the daily rollup keeps the history."""
from dataclasses import dataclass
from datetime import timedelta

import pytest_asyncio
from sqlalchemy import func, select

from app.core.security import hash_opaque_token
from app.models import Device, TelemetryDailyRollup, TelemetrySnapshot
from app.models.base import utcnow
from app.repositories.telemetry import TelemetryRepository


@dataclass
class _Dev:
    """Just the ids — avoids touching a Device detached from its creating session."""
    id: object
    org_id: object


async def _make_device(session_factory, org, hostname, machine_id) -> _Dev:
    async with session_factory() as session:
        device = Device(
            org_id=org.id, hostname=hostname, machine_id=machine_id,
            os_version="Windows 11", agent_version="0.6.4",
            token_hash=hash_opaque_token(f"tok-{machine_id}"), last_seen_at=utcnow(),
        )
        session.add(device)
        await session.commit()
        return _Dev(id=device.id, org_id=device.org_id)


@pytest_asyncio.fixture
async def enrolled_device(session_factory, org) -> _Dev:
    return await _make_device(session_factory, org, "PC-RETENTION", "m-retention")


@pytest_asyncio.fixture
async def second_device(session_factory, org) -> _Dev:
    return await _make_device(session_factory, org, "PC-OTHER", "m-other")


def _snap(device, when, cpu, ram_used, free_gb, total_gb=100.0):
    return TelemetrySnapshot(
        device_id=device.id, org_id=device.org_id,
        cpu_percent=cpu, ram_total_mb=16384, ram_used_mb=ram_used,
        disks=[{"drive": "C:", "total_gb": total_gb, "used_gb": total_gb - free_gb, "free_gb": free_gb}],
        collected_at=when,
    )


async def test_rollup_accumulates_avg_and_max(session_factory, enrolled_device):
    async with session_factory() as session:
        repo = TelemetryRepository(session)
        now = utcnow()
        for cpu, ram, free in [(10.0, 1000, 50.0), (50.0, 3000, 20.0), (30.0, 2000, 40.0)]:
            snap = await repo.add_snapshot(_snap(enrolled_device, now, cpu, ram, free))
            await repo.roll_up_snapshot(snap)
        await session.commit()

        rows = await repo.get_rollups(enrolled_device.id)
        assert len(rows) == 1                      # same UTC day → one row
        r = rows[0]
        assert r.samples == 3
        assert r.cpu_avg == 30.0                   # (10+50+30)/3
        assert r.cpu_max == 50.0
        assert r.ram_used_avg_mb == 2000
        assert r.ram_used_max_mb == 3000
        assert r.disk_free_min_pct == 20.0         # worst free% of the day


async def test_prune_drops_old_snapshots_but_keeps_rollup(session_factory, enrolled_device):
    async with session_factory() as session:
        repo = TelemetryRepository(session)
        now = utcnow()
        old = await repo.add_snapshot(_snap(enrolled_device, now - timedelta(days=30), 80.0, 9000, 5.0))
        await repo.roll_up_snapshot(old)
        fresh = await repo.add_snapshot(_snap(enrolled_device, now, 20.0, 2000, 60.0))
        await repo.roll_up_snapshot(fresh)
        await session.commit()

        # keep_min_rows=1 so the floor keeps only the newest and the old row is eligible.
        removed = await repo.prune_snapshots(enrolled_device.id, keep_days=7, keep_min_rows=1)
        await session.commit()
        assert removed == 1                                    # only the 30-day-old row

        remaining = (await session.execute(
            select(func.count()).select_from(TelemetrySnapshot)
            .where(TelemetrySnapshot.device_id == enrolled_device.id)
        )).scalar_one()
        assert remaining == 1

        # The pruned day's history survives as a rollup — two distinct days.
        rollups = (await session.execute(
            select(func.count()).select_from(TelemetryDailyRollup)
            .where(TelemetryDailyRollup.device_id == enrolled_device.id)
        )).scalar_one()
        assert rollups == 2


async def test_prune_disabled_keeps_everything(session_factory, enrolled_device):
    async with session_factory() as session:
        repo = TelemetryRepository(session)
        await repo.add_snapshot(_snap(enrolled_device, utcnow() - timedelta(days=365), 5.0, 500, 90.0))
        await session.commit()
        assert await repo.prune_snapshots(enrolled_device.id, keep_days=0) == 0


async def test_prune_is_scoped_to_one_device(session_factory, enrolled_device, second_device):
    """A device reporting in must never delete another device's history."""
    async with session_factory() as session:
        repo = TelemetryRepository(session)
        stale = utcnow() - timedelta(days=30)
        for d in (enrolled_device, second_device):
            await repo.add_snapshot(_snap(d, stale, 10.0, 1000, 50.0))
            await repo.add_snapshot(_snap(d, stale + timedelta(minutes=1), 11.0, 1100, 50.0))
        await session.commit()

        await repo.prune_snapshots(enrolled_device.id, keep_days=7, keep_min_rows=1)
        await session.commit()

        others = (await session.execute(
            select(func.count()).select_from(TelemetrySnapshot)
            .where(TelemetrySnapshot.device_id == second_device.id)
        )).scalar_one()
        assert others == 2                                     # untouched


async def test_floor_keeps_newest_even_when_all_are_ancient(session_factory, enrolled_device):
    """A device back from a long offline spell flushes only stale telemetry — it must not
    be left with zero snapshots, or the portal reports 'no telemetry yet'."""
    async with session_factory() as session:
        repo = TelemetryRepository(session)
        ancient = utcnow() - timedelta(days=45)
        for i in range(5):
            await repo.add_snapshot(_snap(enrolled_device, ancient + timedelta(minutes=i), 10.0, 1000, 50.0))
        await session.commit()

        removed = await repo.prune_snapshots(enrolled_device.id, keep_days=7, keep_min_rows=60)
        await session.commit()
        assert removed == 0                                    # floor protects all five

        assert await repo.get_latest_snapshot(enrolled_device.id) is not None
