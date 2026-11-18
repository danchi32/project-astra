"""Phase 3 · AI Smart Guard: the org's browser policy (D10/D1/D2) and each PC's status.

Behind the `ai_guard` entitlement, which no plan includes: an operator turns it on per
organization. Editing is admin-only and audited. Staff can read the status.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles, requires
from app.core.database import get_db
from app.models import Device, User, UserRole
from app.services import browser_policy, guard_approvals, guard_discovery, guard_events, guard_suggestions
from app.services.browser_policy import BrowserPolicyBody, BrowserResult
from app.services.entitlements import AI_GUARD

router = APIRouter(prefix="/guard", tags=["guard"], dependencies=[Depends(requires(AI_GUARD))])


class BrowserPolicyRead(BaseModel):
    version: int
    policy: BrowserPolicyBody
    updated_at: datetime | None
    # E8: while set, the extension only records. For an org with no policy yet, when the pilot
    # would end if it started now.
    pilot_until: datetime | None = None


def _read(row, policy: BrowserPolicyBody | None = None) -> BrowserPolicyRead:
    return BrowserPolicyRead(version=row.version, policy=policy or BrowserPolicyBody(**row.policy),
                             updated_at=row.updated_at, pilot_until=browser_policy.pilot_until(row))


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
        return BrowserPolicyRead(version=0, policy=BrowserPolicyBody(), updated_at=None,
                                 pilot_until=browser_policy.pilot_until(None))
    policy = BrowserPolicyBody(**row.policy)
    if actor.role != UserRole.ADMIN:
        # Restricted keywords are often client or project code names: admins only (review L1).
        policy = policy.model_copy(update={"guard_keywords": []})
    return _read(row, policy)


@router.put("/browser-policy", response_model=BrowserPolicyRead,
            summary="Set the organization's browser policy (admin; audited)",
            responses={409: {"description": "A mode other than record-only during the 14-day pilot"}})
async def put_browser_policy(
    body: BrowserPolicyBody,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> BrowserPolicyRead:
    try:
        return _read(await browser_policy.put(session, actor=actor, body=body))
    except browser_policy.PilotActive as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from None


@router.post("/browser-policy/end-pilot", response_model=BrowserPolicyRead,
             summary="End the 14-day record-only pilot early (admin; audited)")
async def end_pilot(
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> BrowserPolicyRead:
    try:
        return _read(await browser_policy.end_pilot(session, actor=actor))
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There is no pilot running.") from None


class SiteCategoryRead(BaseModel):
    key: str
    label: str
    hosts: list[str]


@router.get("/site-categories", response_model=list[SiteCategoryRead],
            summary="The kinds of site the browser policy can block, and what each covers (staff)")
async def site_categories(
    actor: User = Depends(require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)),
) -> list[SiteCategoryRead]:
    return [SiteCategoryRead(key=k, label=label, hosts=list(hosts))
            for k, (label, hosts) in browser_policy.SITE_CATEGORIES.items()]


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
    justified: int
    redacted: int
    blocked: int
    unknown: int
    went_ahead: int
    stopped: int
    reasons: dict[str, int]
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
    outcome: str | None
    reason: str | None


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
                           keyword_hits=e.keyword_hits, unknown=e.unknown, outcome=e.outcome, reason=e.reason)
            for e, host in await guard_events.recent(session, actor.org_id, days, limit, offset)]


# ── D5: where sensitive files are. Folder paths name people, so admins only. ───────────────

class DiscoveryFolderRead(BaseModel):
    path: str
    files: int
    files_with_findings: int
    counts: dict[str, int]
    contact_lists: int


class DiscoveryDeviceRead(BaseModel):
    device_id: uuid.UUID
    hostname: str
    scanned_at: datetime
    files_scanned: int
    files_skipped: int
    truncated: bool
    folders: list[DiscoveryFolderRead]


class DiscoveryRead(BaseModel):
    pcs: int
    files_with_findings: int
    contact_lists: int
    kinds: dict[str, int]
    devices: list[DiscoveryDeviceRead]


@router.get("/discovery", response_model=DiscoveryRead,
            summary="Where sensitive files are on the organization's PCs, by folder, counts only (admin)")
async def discovery(
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> DiscoveryRead:
    return DiscoveryRead(**await guard_discovery.for_org(session, actor.org_id))


# ── D5 slice 2: policy suggestions from the map and the events. Admin only; audited. ───────

class SuggestionRead(BaseModel):
    key: str
    title: str
    why: str
    changes: list[str]


@router.get("/suggestions", response_model=list[SuggestionRead],
            summary="Policy changes suggested by what AI Guard has seen, with the evidence (admin)")
async def list_suggestions(
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> list[SuggestionRead]:
    return [SuggestionRead(**s) for s in await guard_suggestions.suggestions(session, actor.org_id)]


class ApplySuggestionBody(BaseModel):
    """The changes as the admin's screen showed them: if the evidence has since changed what
    the suggestion would do, it is refused rather than applied (security review L3)."""
    model_config = ConfigDict(extra="forbid")
    changes: list[str] = Field(max_length=10)


@router.post("/suggestions/{key}/apply", response_model=BrowserPolicyRead,
             summary="Apply one suggestion to the browser policy (admin; audited)")
async def apply_suggestion(
    key: str,
    body: ApplySuggestionBody,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> BrowserPolicyRead:
    try:
        row = await guard_suggestions.apply(session, actor=actor, key=key, seen_changes=body.changes)
    except guard_suggestions.SuggestionNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That suggestion no longer applies.") from None
    except (guard_suggestions.SuggestionChanged, browser_policy.PilotActive) as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from None
    return _read(row)


@router.post("/suggestions/{key}/dismiss", status_code=status.HTTP_204_NO_CONTENT,
             summary="Hide one suggestion for good (admin; audited)")
async def dismiss_suggestion(
    key: str,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> None:
    try:
        await guard_suggestions.dismiss(session, actor=actor, key=key)
    except guard_suggestions.SuggestionNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That suggestion no longer applies.") from None


# ── D7: approvals. Admin only; every decision is audited. ──────────────────────────────────

class GuardApprovalRead(BaseModel):
    id: uuid.UUID
    device_id: uuid.UUID
    hostname: str
    windows_user: str
    site: str
    channel: str
    counts: dict[str, int]
    contact_list: bool
    keyword_hits: int
    status: str            # pending | approved | denied | expired | ended
    requested_at: datetime
    decided_at: datetime | None
    valid_until: datetime | None


class DecideBody(BaseModel):
    """`requested_at` is the request's time as the admin's screen showed it: a request that
    changed since then is refused, so an approval always covers what the admin looked at."""
    model_config = ConfigDict(extra="forbid")
    requested_at: datetime


class ApproveBody(DecideBody):
    minutes: int = Field(guard_approvals.DEFAULT_MINUTES, ge=guard_approvals.MIN_MINUTES, le=guard_approvals.MAX_MINUTES)


def _approval(a, host: str) -> GuardApprovalRead:
    return GuardApprovalRead(id=a.id, device_id=a.device_id, hostname=host, windows_user=a.windows_user,
                             site=a.site, channel=a.channel, counts=a.counts, contact_list=a.contact_list,
                             keyword_hits=a.keyword_hits, status=guard_approvals.status_of(a),
                             requested_at=a.requested_at, decided_at=a.decided_at, valid_until=a.valid_until)


@router.get("/approvals", response_model=list[GuardApprovalRead],
            summary="Requests to let a held paste or upload through, newest first (admin)")
async def list_approvals(
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> list[GuardApprovalRead]:
    return [_approval(a, host) for a, host in await guard_approvals.list_for_org(session, actor.org_id)]


async def _decide(session, actor, approval_id, approve: bool, minutes: int, seen) -> GuardApprovalRead:
    try:
        a = await guard_approvals.decide(session, actor=actor, approval_id=approval_id, approve=approve,
                                         minutes=minutes, seen_requested_at=seen)
    except guard_approvals.ApprovalNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such request.") from None
    except guard_approvals.ApprovalClosed as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from None
    host = (await session.get(Device, a.device_id)).hostname
    return _approval(a, host)


@router.post("/approvals/{approval_id}/approve", response_model=GuardApprovalRead,
             summary="Let it through for that person, PC, site and channel, for a set time (admin; audited)")
async def approve(
    approval_id: uuid.UUID,
    body: ApproveBody,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> GuardApprovalRead:
    return await _decide(session, actor, approval_id, True, body.minutes, body.requested_at)


@router.post("/approvals/{approval_id}/deny", response_model=GuardApprovalRead,
             summary="Refuse a request (admin; audited)")
async def deny(
    approval_id: uuid.UUID,
    body: DecideBody,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> GuardApprovalRead:
    return await _decide(session, actor, approval_id, False, 0, body.requested_at)
