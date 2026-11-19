"""Phase 3 · AI Smart Guard: the org's browser policy (D10/D1/D2) and each PC's status.

Behind the `ai_guard` entitlement, which no plan includes: an operator turns it on per
organization. Editing is admin-only and audited. Staff can read the status.
"""
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles, requires
from app.core.database import get_db
from app.models import Device, DeviceInstalledApp, User, UserRole
from app.services import (
    browser_policy,
    guard_approvals,
    guard_cases,
    guard_discovery,
    guard_events,
    guard_suggestions,
)
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
    # D1: which policy this PC should be on now: a group's name, or None for the org's.
    policy_group: str | None = None
    policy_version: int = 0
    # D10: browsers the policy does not reach that are installed here, from the app inventory.
    other_browsers: list[str] = Field(default_factory=list)
    # C3: this PC's USB mode (from its own policy), and until when it may write to USB drives, if
    # IT opened a window ("write on request").
    usb_mode: str = "off"
    usb_write_until: datetime | None = None


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
    states = await browser_policy.device_states(session, actor.org_id)
    org = await browser_policy.get(session, actor.org_id)
    groups = await browser_policy.applies_to(session, actor.org_id, {s.device_id for s, _ in states})
    apps: dict = {}
    for did, app in (await session.execute(
            select(DeviceInstalledApp.device_id, DeviceInstalledApp.name)
            .where(DeviceInstalledApp.org_id == actor.org_id,
                   or_(*(func.lower(DeviceInstalledApp.name).like(p + "%")
                         for p in browser_policy.OTHER_BROWSERS.values()))))).all():
        apps.setdefault(did, []).append(app)
    windows = await browser_policy.usb_windows(session, actor.org_id)
    out = []
    for s, host in states:
        name, row = groups.get(s.device_id, (None, org))
        out.append(DeviceBrowserState(device_id=s.device_id, hostname=host, version=s.version,
                                      results=[BrowserResult(**r) for r in s.results], reported_at=s.reported_at,
                                      policy_group=name, policy_version=row.version if row else 0,
                                      other_browsers=browser_policy.other_browsers(apps.get(s.device_id, [])),
                                      usb_mode=((row.policy if row else None) or {}).get("usb_mode", "off"),
                                      usb_write_until=windows.get(s.device_id)))
    return out


# ── D1: a device group's own policy ───────────────────────────────────────────────────────────

class GroupPolicyRead(BaseModel):
    group_id: uuid.UUID
    group_name: str
    priority: int
    version: int
    policy: BrowserPolicyBody
    updated_at: datetime


class GroupPolicyWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Lower wins when a PC is in more than one group with a policy.
    priority: int = Field(ge=1, le=1000)
    policy: BrowserPolicyBody


@router.get("/group-policies", response_model=list[GroupPolicyRead],
            summary="Device groups with a browser policy of their own, in the order they win (staff)")
async def list_group_policies(
    actor: User = Depends(require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)),
    session: AsyncSession = Depends(get_db),
) -> list[GroupPolicyRead]:
    out = []
    for row, name in await browser_policy.group_policies(session, actor.org_id):
        policy = BrowserPolicyBody(**row.policy)
        if actor.role != UserRole.ADMIN:
            policy = policy.model_copy(update={"guard_keywords": []})   # as for the org's policy (review L1)
        out.append(GroupPolicyRead(group_id=row.group_id, group_name=name, priority=row.priority,
                                   version=row.version, policy=policy, updated_at=row.updated_at))
    return out


@router.put("/group-policies/{group_id}", response_model=GroupPolicyRead,
            summary="Give a device group its own browser policy, or change it (admin; audited)",
            responses={404: {"description": "No such group"},
                        409: {"description": "No org policy yet, or a mode other than record-only in the pilot"}})
async def put_group_policy(
    group_id: uuid.UUID,
    body: GroupPolicyWrite,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> GroupPolicyRead:
    try:
        row = await browser_policy.put_group(session, actor=actor, group_id=group_id,
                                             priority=body.priority, body=body.policy)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such group.") from None
    except (browser_policy.NoOrgPolicy, browser_policy.PilotActive) as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from None
    name = next(n for r, n in await browser_policy.group_policies(session, actor.org_id) if r.group_id == group_id)
    return GroupPolicyRead(group_id=row.group_id, group_name=name, priority=row.priority, version=row.version,
                           policy=BrowserPolicyBody(**row.policy), updated_at=row.updated_at)


@router.delete("/group-policies/{group_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Remove a group's own policy; its PCs go back to the org's (admin; audited)")
async def delete_group_policy(
    group_id: uuid.UUID,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> None:
    try:
        await browser_policy.delete_group(session, actor=actor, group_id=group_id)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That group has no policy of its own.") from None


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
    origin: str | None = None   # C2: where an uploaded file was downloaded from


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
                           keyword_hits=e.keyword_hits, unknown=e.unknown, outcome=e.outcome, reason=e.reason,
                           origin=e.origin)
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


# ── C3: USB write windows ─────────────────────────────────────────────────────────────────────

class UsbWindowWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    minutes: int = Field(ge=browser_policy.USB_WINDOW_MINUTES[0], le=browser_policy.USB_WINDOW_MINUTES[1])


class UsbWindowRead(BaseModel):
    device_id: uuid.UUID
    until: datetime


@router.post("/devices/{device_id}/usb-window", response_model=UsbWindowRead,
             summary="Let one PC write to USB drives for a while, in 'write on request' mode (admin; audited)")
async def open_usb_window(
    device_id: uuid.UUID,
    body: UsbWindowWrite,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> UsbWindowRead:
    try:
        row = await browser_policy.open_usb_window(session, actor=actor, device_id=device_id, minutes=body.minutes)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such PC.") from None
    except browser_policy.NotOnRequest as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from None
    return UsbWindowRead(device_id=row.device_id, until=row.until)


@router.delete("/devices/{device_id}/usb-window", status_code=status.HTTP_204_NO_CONTENT,
               summary="End a USB write window early (admin; audited)")
async def close_usb_window(
    device_id: uuid.UUID,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> None:
    try:
        await browser_policy.close_usb_window(session, actor=actor, device_id=device_id)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No window is open on that PC.") from None


# ── C1: cases, not alerts ─────────────────────────────────────────────────────────────────────
# A case names a person, so, like events about named people, admins only.

class CaseSite(BaseModel):
    site: str
    kind: str | None
    new: bool
    events: int
    items: int
    contact_lists: int
    went_ahead: int
    blocked: int
    channels: list[str]
    origins: list[str] = Field(default_factory=list)   # C2: where its files were downloaded from


class CaseRead(BaseModel):
    id: uuid.UUID
    windows_user: str
    opened_at: datetime
    last_event_at: datetime
    status: str
    resolution: str | None
    score: int
    level: str
    reasons: list[str]
    sites: list[CaseSite]
    kinds: dict[str, int]
    events: int
    devices: list[str]
    closed_at: datetime | None


class CasesRead(BaseModel):
    open: dict[str, int]
    quiet_sites: list[str]
    quiet_events_30d: int
    cases: list[CaseRead]


def _case(c) -> CaseRead:
    s = c.summary or {}
    return CaseRead(id=c.id, windows_user=c.windows_user, opened_at=c.opened_at, last_event_at=c.last_event_at,
                    status=c.status, resolution=c.resolution, score=c.score, level=c.level,
                    reasons=s.get("reasons", []), sites=s.get("sites", []), kinds=s.get("kinds", {}),
                    events=s.get("events", 0), devices=s.get("devices", []), closed_at=c.closed_at)


@router.get("/cases", response_model=CasesRead,
            summary="AI Guard cases: each person's sensitive-data events as one ranked story (admin)")
async def list_cases(
    status_: Literal["open", "closed"] = Query("open", alias="status"),
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> CasesRead:
    overview = await guard_cases.overview(session, actor.org_id)
    return CasesRead(**overview, cases=[_case(c) for c in await guard_cases.cases(session, actor.org_id, status_)])


class CloseCaseBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resolution: Literal["expected", "handled"]
    # "Stop raising cases for this site": only a site in this case, only when closed as expected.
    quiet_site: str | None = Field(default=None, max_length=253)


@router.post("/cases/{case_id}/close", response_model=CaseRead,
             summary="Close a case as expected or handled; optionally make one of its sites quiet (admin; audited)")
async def close_case(
    case_id: uuid.UUID,
    body: CloseCaseBody,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> CaseRead:
    try:
        return _case(await guard_cases.close(session, actor=actor, case_id=case_id, resolution=body.resolution,
                                             quiet_site=body.quiet_site))
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such case.") from None
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from None


@router.delete("/quiet-sites/{site}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Let a quiet site raise cases again (admin; audited)")
async def remove_quiet_site(
    site: str,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> None:
    try:
        await guard_cases.unquiet(session, actor=actor, site=site)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That site is not quiet.") from None
