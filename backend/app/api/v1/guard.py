"""Phase 3 · AI Smart Guard: the org's browser policy (D10/D1/D2) and each PC's status.

Behind the `ai_guard` entitlement, which no plan includes: an operator turns it on per
organization. Editing is admin-only and audited. Staff can read the status.
"""
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
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
    # Which policy this PC should be on now: a named policy's name, or None for the default. It
    # follows the person the PC is assigned to in Assets (`assigned_to`).
    policy_name: str | None = None
    exceptions: list[str] = Field(default_factory=list)   # names of the exceptions laid over it
    assigned_to: str | None = None
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
    ids = {s.device_id for s, _ in states}
    covered = await browser_policy.applies_to(session, actor.org_id, ids)
    owners = await browser_policy.assigned_users(session, actor.org_id, ids)
    names = dict((await session.execute(select(User.id, User.full_name).where(
        User.org_id == actor.org_id, User.id.in_(set(owners.values()))))).all()) if owners else {}
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
        full, exceptions = covered.get(s.device_id, (None, []))
        version, policy = browser_policy.layered(full or org, exceptions) if (full or org) else (0, {})
        out.append(DeviceBrowserState(device_id=s.device_id, hostname=host, version=s.version,
                                      results=[BrowserResult(**r) for r in s.results], reported_at=s.reported_at,
                                      policy_name=full.name if full else None, exceptions=[e.name for e in exceptions],
                                      policy_version=version, assigned_to=names.get(owners.get(s.device_id)),
                                      other_browsers=browser_policy.other_browsers(apps.get(s.device_id, [])),
                                      usb_mode=policy.get("usb_mode", "off"), usb_write_until=windows.get(s.device_id)))
    return out


# ── Named policies, for user teams and single users ──────────────────────────────────────────

class NamedPolicyRead(BaseModel):
    id: uuid.UUID
    name: str
    priority: int
    kind: Literal["full", "exception"]
    team_ids: list[uuid.UUID]
    user_ids: list[uuid.UUID]
    version: int
    policy: BrowserPolicyBody | None = None          # a full policy's settings
    exception: browser_policy.ExceptionBody | None = None   # an exception's modules
    updated_at: datetime


class NamedPolicyWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    # Lower wins when a person is named by more than one policy (directly or by a team).
    priority: int = Field(ge=1, le=1000)
    team_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)
    user_ids: list[uuid.UUID] = Field(default_factory=list, max_length=1000)
    # A full policy sends `policy`; an exception, which changes only some modules of whatever full
    # policy the person gets, sends `exception`.
    kind: Literal["full", "exception"] = "full"
    policy: BrowserPolicyBody | None = None
    exception: browser_policy.ExceptionBody | None = None

    @model_validator(mode="after")
    def _one_body(self) -> "NamedPolicyWrite":
        if (self.policy is None) != (self.kind == "exception") or (self.exception is None) != (self.kind == "full"):
            raise ValueError("A full policy sends `policy`; an exception sends `exception`")
        return self

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v or browser_policy.has_control(v):
            raise ValueError("Give the policy a name")
        return v


def _named(row, keywords: bool = True) -> NamedPolicyRead:
    common = {"id": row.id, "name": row.name, "priority": row.priority, "kind": row.kind, "team_ids": row.team_ids,
              "user_ids": row.user_ids, "version": row.version, "updated_at": row.updated_at}
    if row.kind == "exception":
        return NamedPolicyRead(**common, exception=browser_policy.ExceptionBody(**row.policy))
    policy = BrowserPolicyBody(**row.policy)
    if not keywords:
        policy = policy.model_copy(update={"guard_keywords": []})   # as for the default policy (review L1)
    return NamedPolicyRead(**common, policy=policy)


@router.get("/policies", response_model=list[NamedPolicyRead],
            summary="The organization's named browser policies, in the order they win (staff)")
async def list_named_policies(
    actor: User = Depends(require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)),
    session: AsyncSession = Depends(get_db),
) -> list[NamedPolicyRead]:
    return [_named(r, actor.role == UserRole.ADMIN) for r in await browser_policy.named_policies(session, actor.org_id)]


async def _put_named(session, actor, policy_id, body: NamedPolicyWrite) -> NamedPolicyRead:
    try:
        row = await browser_policy.put_named(
            session, actor=actor, policy_id=policy_id, name=body.name, priority=body.priority,
            targets=browser_policy.PolicyTargets(team_ids=body.team_ids, user_ids=body.user_ids),
            body=body.policy or body.exception)
    except LookupError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from None
    except (browser_policy.NoOrgPolicy, browser_policy.PilotActive, browser_policy.DuplicateName,
            browser_policy.WrongKind) as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from None
    return _named(row)


_NAMED_ERRORS = {404: {"description": "No such policy, team or user"},
                 409: {"description": "No default policy yet, a name in use, a change of kind, or a mode other than "
                                         "record-only in the pilot"}}


@router.post("/policies", response_model=NamedPolicyRead, status_code=status.HTTP_201_CREATED,
             summary="Create a browser policy for chosen teams and users (admin; audited)", responses=_NAMED_ERRORS)
async def create_named_policy(
    body: NamedPolicyWrite,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> NamedPolicyRead:
    return await _put_named(session, actor, None, body)


@router.put("/policies/{policy_id}", response_model=NamedPolicyRead,
            summary="Change a named browser policy or who it is for (admin; audited)", responses=_NAMED_ERRORS)
async def update_named_policy(
    policy_id: uuid.UUID,
    body: NamedPolicyWrite,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> NamedPolicyRead:
    return await _put_named(session, actor, policy_id, body)


@router.delete("/policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Delete a named policy; its people's PCs go back to the default (admin; audited)")
async def delete_named_policy(
    policy_id: uuid.UUID,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> None:
    try:
        await browser_policy.delete_named(session, actor=actor, policy_id=policy_id)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such policy.") from None


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
    old: int | None = None   # I1: files with findings unchanged for two years (None: not counted)


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
    if row is None:   # a Tracker suggestion applied where the org has no browser policy yet
        return BrowserPolicyRead(version=0, policy=BrowserPolicyBody(), updated_at=None,
                                 pilot_until=browser_policy.pilot_until(None))
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
    reason: str | None = None   # C3b: why a USB write request was made (a code)


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
                             requested_at=a.requested_at, decided_at=a.decided_at, valid_until=a.valid_until,
                             reason=a.reason)


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


# ── I1: DPDP readiness ──────────────────────────────────────────────────────────────────────

class DpdpItem(BaseModel):
    key: str
    title: str
    why: str
    status: Literal["done", "todo"]
    detail: str
    link: str


class RetentionRead(BaseModel):
    hostname: str
    path: str
    old: int
    files_with_findings: int
    contact_lists: int


class DpdpRead(BaseModel):
    score: int
    done: int
    total: int
    items: list[DpdpItem]
    retention: list[RetentionRead]
    map: dict
    contact: dict
    disclaimer: str
    generated_at: datetime


@router.get("/dpdp", response_model=DpdpRead,
            summary="I1: DPDP readiness from SAVIO's own records: score, tasks, where personal data is (admin)")
async def dpdp_readiness(
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> DpdpRead:
    from app.services import dpdp

    return DpdpRead(**await dpdp.readiness(session, actor.org_id))


class PrivacyContactWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        if v and browser_policy.has_control(v):
            raise ValueError("A name must be plain text")
        return v or None


@router.put("/dpdp/contact", status_code=status.HTTP_204_NO_CONTENT,
            summary="I1: who handles privacy complaints and breaches (admin; audited)")
async def set_privacy_contact(
    body: PrivacyContactWrite,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> None:
    from app.services import dpdp

    await dpdp.set_contact(session, actor=actor, name=body.name, email=body.email)


# ── I1: breach records (the breach workflow; J7 prints one) ─────────────────────────────────

StepKey = Literal["contain", "assess", "counsel", "board", "people", "fix"]   # guard_incidents.STEPS


def _plain(v: str | None, lines: bool = False) -> str | None:
    """Admin text shown on screens and printed: no control or invisible characters (new lines
    allowed where a paragraph is expected)."""
    if v is None:
        return None
    v = v.replace("\r\n", "\n").strip()
    if browser_policy.has_control(v.replace("\n", "") if lines else v):
        raise ValueError("must be plain text")
    return v


class IncidentStep(BaseModel):
    key: StepKey
    title: str
    help: str
    optional: bool
    state: Literal["done", "not_needed"] | None = None
    at: datetime | None = None
    by: str | None = None
    note: str | None = None


class IncidentRead(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID | None
    title: str
    what_happened: str
    found_at: datetime
    kinds: list[str]
    people_affected: int | None
    status: Literal["open", "closed"]
    opened_at: datetime
    closed_at: datetime | None
    steps: list[IncidentStep]


class IncidentDetail(IncidentRead):
    case: dict | None
    timeline: list[dict]


class IncidentFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    what_happened: str = Field(default="", max_length=4000)
    found_at: datetime
    kinds: list[browser_policy.FindingKind] = Field(default_factory=list, max_length=7)
    people_affected: int | None = Field(default=None, ge=0, le=100_000_000)

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        v = _plain(v)
        if not v:
            raise ValueError("A title is needed")
        return v

    @field_validator("what_happened")
    @classmethod
    def _what(cls, v: str) -> str:
        return _plain(v, lines=True)

    @field_validator("found_at")
    @classmethod
    def _found(cls, v: datetime) -> datetime:
        v = v if v.tzinfo else v.replace(tzinfo=UTC)
        if v > datetime.now(UTC) + timedelta(minutes=5):
            raise ValueError("found_at is in the future")
        return v

    @field_validator("kinds")
    @classmethod
    def _kinds(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(v))


class IncidentOpen(IncidentFacts):
    case_id: uuid.UUID | None = None


class StepWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: StepKey
    state: Literal["done", "not_needed"] | None
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("note")
    @classmethod
    def _note(cls, v: str | None) -> str | None:
        return _plain(v, lines=True) or None


class IncidentPatch(BaseModel):
    """Any of the facts, one step, and/or closing (true) or reopening (false)."""
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=200)
    what_happened: str | None = Field(default=None, max_length=4000)
    found_at: datetime | None = None
    kinds: list[browser_policy.FindingKind] | None = Field(default=None, max_length=7)
    people_affected: int | None = Field(default=None, ge=0, le=100_000_000)
    step: StepWrite | None = None
    closed: bool | None = None

    @field_validator("title", "what_happened", "found_at", "kinds")
    @classmethod
    def _same_rules(cls, v, info):
        # The same checks as when opening; None means "not given" here and is refused later.
        if v is None:
            return None
        return {"title": IncidentFacts._title, "what_happened": IncidentFacts._what,
                "found_at": IncidentFacts._found, "kinds": IncidentFacts._kinds}[info.field_name](v)


@router.get("/incidents", response_model=list[IncidentRead],
            summary="I1: the organization's breach records, open first (admin)")
async def list_incidents(
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> list[IncidentRead]:
    from app.services import guard_incidents

    return [IncidentRead(**r) for r in await guard_incidents.list_for(session, actor.org_id)]


@router.post("/incidents", response_model=IncidentRead, status_code=status.HTTP_201_CREATED,
             summary="I1: start a breach record, from a case or on its own (admin; audited)")
async def open_incident(
    body: IncidentOpen,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> IncidentRead:
    from app.services import guard_incidents

    row = await guard_incidents.open_(session, actor=actor, **body.model_dump())
    return IncidentRead(**guard_incidents.read(row))


@router.get("/incidents/{incident_id}", response_model=IncidentDetail,
            summary="I1: one breach record with its case and its timeline (admin)")
async def get_incident(
    incident_id: uuid.UUID,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> IncidentDetail:
    from app.services import guard_incidents

    row = await guard_incidents.get(session, actor.org_id, incident_id)
    return IncidentDetail(**await guard_incidents.detail(session, row))


@router.patch("/incidents/{incident_id}", response_model=IncidentRead,
              summary="I1: edit a breach record's facts, settle a step, close or reopen it (admin; audited)")
async def update_incident(
    incident_id: uuid.UUID,
    body: IncidentPatch,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> IncidentRead:
    from app.services import guard_incidents

    row = await guard_incidents.get(session, actor.org_id, incident_id)
    fields = body.model_dump(exclude_unset=True, exclude={"step", "closed"})
    if any(v is None for k, v in fields.items() if k != "people_affected"):
        raise HTTPException(422, "Only the number of people can be cleared")
    row = await guard_incidents.update(session, actor=actor, row=row, fields=fields,
                                       step=body.step.model_dump() if body.step else None, close=body.closed)
    return IncidentRead(**guard_incidents.read(row))


# ── C3b: USB drives the PCs have seen, for approving company drives ─────────────────────────

class DriveSeenRead(BaseModel):
    id: str
    name: str
    unique_serial: bool
    pcs: list[str]
    last_seen: datetime
    approved_in: list[str]   # "Everyone" and/or names of the policies that already approve it


@router.get("/drives", response_model=list[DriveSeenRead],
            summary="USB drives the organization's PCs have used, and where each is approved (admin)")
async def drives_seen(
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> list[DriveSeenRead]:
    return [DriveSeenRead(**d) for d in await browser_policy.drives_seen(session, actor.org_id)]


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
    origins: list[str] = Field(default_factory=list)   # C2: where its files were likely downloaded from
    pcs: list[str] = Field(default_factory=list)       # review 3b L2: the PCs its events came from


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


class CaseAction(BaseModel):
    device_id: uuid.UUID
    hostname: str
    action_id: str
    label: str
    params: dict[str, str]
    available: bool
    why: str | None


@router.get("/cases/{case_id}/actions", response_model=list[CaseAction],
            summary="C4: the fixes SAVIO offers for a case, per PC: existing remediation actions (admin)")
async def case_actions(
    case_id: uuid.UUID,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> list[CaseAction]:
    try:
        return [CaseAction(**a) for a in await guard_cases.actions(session, actor.org_id, case_id)]
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such case.") from None


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
