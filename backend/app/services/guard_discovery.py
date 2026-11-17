"""Phase 3 · D5: where sensitive files are on the org's PCs, by folder, in counts.

The scan runs on the PC, inside the native host that E4 keeps off the network. What arrives
here is one line per folder where something was found: its path, files read, files with
findings, counts per kind, contact lists. No file names, no content. Each PC's latest map
replaces its previous one. Admins only: folder paths name people ("C:\\Users\\asha\\...").
"""
from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, GuardDiscovery
from app.models.base import utcnow
from app.services.browser_policy import FindingKind, entitled, has_control

MAX_FOLDERS = 500


class DiscoveryFolderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=400)
    files: int = Field(ge=0, le=1_000_000)
    files_with_findings: int = Field(ge=0, le=1_000_000)
    counts: dict[FindingKind, int] = Field(default_factory=dict, max_length=7)
    contact_lists: int = Field(default=0, ge=0, le=1_000_000)

    @field_validator("path")
    @classmethod
    def _path(cls, v: str) -> str:
        if has_control(v):
            raise ValueError("path has control or invisible characters")
        return v

    @field_validator("counts")
    @classmethod
    def _counts(cls, v: dict[str, int]) -> dict[str, int]:
        if any(not 0 <= n <= 100_000_000 for n in v.values()):
            raise ValueError("counts out of range")
        return {k: n for k, n in v.items() if n > 0}


class DiscoveryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scanned_at: datetime
    files_scanned: int = Field(ge=0, le=10_000_000)
    files_skipped: int = Field(ge=0, le=10_000_000)
    truncated: bool = False
    folders: list[DiscoveryFolderIn] = Field(default_factory=list, max_length=MAX_FOLDERS)

    @field_validator("scanned_at")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        v = v if v.tzinfo else v.replace(tzinfo=UTC)
        if v > utcnow() + timedelta(days=1):
            raise ValueError("scanned_at is in the future")
        return v


async def ingest(session: AsyncSession, device: Device, body: DiscoveryIn) -> bool:
    """This PC's map, replacing the last. Dropped (but accepted) without the add-on."""
    if not await entitled(session, device.org_id):
        return False
    folders = [f.model_dump() for f in body.folders]
    row = await session.get(GuardDiscovery, device.id)
    if row is None:
        session.add(GuardDiscovery(device_id=device.id, org_id=device.org_id, scanned_at=body.scanned_at,
                                   received_at=utcnow(), files_scanned=body.files_scanned,
                                   files_skipped=body.files_skipped, truncated=body.truncated, folders=folders))
    else:
        row.scanned_at, row.received_at = body.scanned_at, utcnow()
        row.files_scanned, row.files_skipped, row.truncated, row.folders = (
            body.files_scanned, body.files_skipped, body.truncated, folders)
    await session.commit()
    return True


async def for_org(session: AsyncSession, org_id) -> dict:
    """Every PC's latest map, and the org's totals: files with each kind, across all PCs."""
    rows = (await session.execute(
        select(GuardDiscovery, Device.hostname)
        .join(Device, Device.id == GuardDiscovery.device_id)
        .where(GuardDiscovery.org_id == org_id)
        .order_by(Device.hostname)
    )).all()
    kinds: Counter[str] = Counter()
    files_with_findings = contact_lists = 0
    devices = []
    for d, host in rows:
        for f in d.folders:
            kinds.update(f.get("counts") or {})
            files_with_findings += f.get("files_with_findings", 0)
            contact_lists += f.get("contact_lists", 0)
        devices.append({
            "device_id": d.device_id, "hostname": host, "scanned_at": d.scanned_at,
            "files_scanned": d.files_scanned, "files_skipped": d.files_skipped, "truncated": d.truncated,
            "folders": sorted(d.folders, key=lambda f: -f.get("files_with_findings", 0)),
        })
    return {
        "pcs": len(devices),
        "files_with_findings": files_with_findings,
        "contact_lists": contact_lists,
        "kinds": dict(kinds.most_common()),
        "devices": devices,
    }
