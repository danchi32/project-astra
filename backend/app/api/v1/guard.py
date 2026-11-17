"""Phase 3 · AI Smart Guard: the org's browser policy (D10/D1/D2) and each PC's status.

Behind the `ai_guard` entitlement, which no plan includes: an operator turns it on per
organization. Editing is admin-only and audited. Staff can read the status.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles, requires
from app.core.database import get_db
from app.models import User, UserRole
from app.services import browser_policy, guard_events
from app.services.browser_policy import BrowserPolicyBody, BrowserResult
from app.services.entitlements import AI_GUARD

router = APIRouter(prefix="/guard", tags=["guard"], dependencies=[Depends(requires(AI_GUARD))])


class BrowserPolicyRead(BaseModel):
    version: int
    policy: BrowserPolicyBody
    updated_at: datetime | None


class DeviceBrowserState(BaseModel):
    device_id: uuid.UUID
    hostname: str
    version: int
    results: list[BrowserResult]
    reported_at: datetime


@router.get("/browser-policy", response_model=BrowserPolicyRead,
            summary="The organization's browser policy (staff)")
async def get_browser_policy(
    actor: User = Depends(require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)),
    session: AsyncSession = Depends(get_db),
) -> BrowserPolicyRead:
    row = await browser_policy.get(session, actor.org_id)
    if row is None:
        return BrowserPolicyRead(version=0, policy=BrowserPolicyBody(), updated_at=None)
    return BrowserPolicyRead(version=row.version, policy=BrowserPolicyBody(**row.policy), updated_at=row.updated_at)


@router.put("/browser-policy", response_model=BrowserPolicyRead,
            summary="Set the organization's browser policy (admin; audited)")
async def put_browser_policy(
    body: BrowserPolicyBody,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> BrowserPolicyRead:
    row = await browser_policy.put(session, actor=actor, body=body)
    return BrowserPolicyRead(version=row.version, policy=BrowserPolicyBody(**row.policy), updated_at=row.updated_at)


@router.get("/browser-policy/devices", response_model=list[DeviceBrowserState],
            summary="What each PC last reported after applying the policy (staff)")
async def browser_policy_devices(
    actor: User = Depends(require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)),
    session: AsyncSession = Depends(get_db),
) -> list[DeviceBrowserState]:
    return [DeviceBrowserState(device_id=s.device_id, hostname=host, version=s.version,
                               results=[BrowserResult(**r) for r in s.results], reported_at=s.reported_at)
            for s, host in await browser_policy.device_states(session, actor.org_id)]


# ── E3: what the extension saw. These name people, so admins only. ─────────────────────────

class SiteCount(BaseModel):
    site: str
    events: int


class PersonCount(BaseModel):
    windows_user: str
    events: int


class GuardEventSummary(BaseModel):
    days: int
    total: int
    allowed: int
    warned: int
    blocked: int
    unknown: int
    kinds: dict[str, int]
    contact_lists: int
    keyword_events: int
    top_sites: list[SiteCount]
    top_people: list[PersonCount]


class GuardEventRead(BaseModel):
    id: uuid.UUID
    occurred_at: datetime
    device_id: uuid.UUID
    hostname: str
    windows_user: str
    site: str
    channel: str
    mode: str
    action: str
    counts: dict[str, int]
    contact_list: bool
    keyword_hits: int
    unknown: bool


@router.get("/events/summary", response_model=GuardEventSummary,
            summary="What the browser extension found, totalled over the last N days (admin)")
async def guard_event_summary(
    days: int = Query(7, ge=1, le=guard_events.RETENTION_DAYS),
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> GuardEventSummary:
    return GuardEventSummary(**await guard_events.summary(session, actor.org_id, days))


@router.get("/events", response_model=list[GuardEventRead],
            summary="Recent browser extension events, newest first: counts only, never content (admin)")
async def list_guard_events(
    days: int = Query(7, ge=1, le=guard_events.RETENTION_DAYS),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0, le=100_000),
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> list[GuardEventRead]:
    return [GuardEventRead(id=e.id, occurred_at=e.occurred_at, device_id=e.device_id, hostname=host,
                           windows_user=e.windows_user, site=e.site, channel=e.channel, mode=e.mode,
                           action=e.action, counts=e.counts, contact_list=e.contact_list,
                           keyword_hits=e.keyword_hits, unknown=e.unknown)
            for e, host in await guard_events.recent(session, actor.org_id, days, limit, offset)]
