"""Workforce Insights ("Tracker") — attendance reads for the portal.

Gated at the router on the `workforce_insights` entitlement, so a new endpoint added to this
file cannot ship ungated by someone forgetting the decorator — the same discipline the
remote-control, compliance and fleet routers use. This is employee-monitoring data, so the
gate is the point, not a formality: without the per-org entitlement there is no route.

Staff only in P1 (admin / technician). Employee self-view and team-manager scoping both need
a Windows-account → directory-user mapping that does not exist yet (daily_user_summary.user_id
is the reserved hook); they arrive with that enrichment, not here.
"""
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles, requires
from app.core.database import get_db
from app.models import Organization, User, UserRole
from app.models.base import utcnow
from app.schemas.workforce import (
    ActivitySegmentRead,
    AttendanceConfigRead,
    AttendanceSettingsWrite,
    CategoryConfigRead,
    CategoryOverrides,
    DailyUserSummaryRead,
    HolidayRead,
    HolidayWrite,
    ShiftAssignmentWrite,
    TeamRollupRead,
    TeamShiftRead,
    TrackedAccountRead,
    UserDetailRead,
    WorkSessionRead,
    WorkShiftRead,
    WorkShiftWrite,
)
from app.services.accounts import AccountService
from app.services.attendance_config import AttendanceConfigService
from app.services.audit import AuditService
from app.services.entitlements import WORKFORCE_INSIGHTS
from app.services.exceptions import ConflictError, NotFoundError
from app.services.shifts import ShiftService
from app.services.workforce import WorkforceService
from app.services.workforce_categories import BUCKETS, builtin_buckets

router = APIRouter(
    prefix="/tracker",
    tags=["workforce insights"],
    dependencies=[Depends(requires(WORKFORCE_INSIGHTS))],
)

staff_required = require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)
# Changing what counts as productive is a policy decision, so it is admin-only — a technician
# can read the config (to understand a score) but not rewrite the org's productivity rules.
admin_required = require_roles(UserRole.ADMIN)

# Cap a single query's span so a wide range can't scan a year of rows by accident; the
# portal pages by moving the date window, not by offset.
_MAX_RANGE_DAYS = 92


async def _audit_view(
    session: AsyncSession,
    actor: User,
    *,
    target_type: str,
    target_id: str | None,
    detail: dict,
) -> None:
    """Record that this staff member looked at employee-monitoring data.

    Non-negotiable per the plan (§6: "viewing the sensitive data is itself audited") — the
    whole point of monitoring is that access to it is accountable. A GET writing an audit row
    is fine: the read-only middleware (app/main.py) gates only write HTTP methods."""
    await AuditService(session).record(
        org_id=actor.org_id,
        actor_id=actor.id,
        action="workforce.view",
        target_type=target_type,
        target_id=target_id,
        detail=detail,
    )
    await session.commit()


@router.get(
    "/attendance",
    response_model=list[DailyUserSummaryRead],
    summary="Per-user attendance (first-in, last-out, worked) over a date range",
)
async def attendance(
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    device_id: uuid.UUID | None = Query(default=None),
    username: str | None = Query(default=None),
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> list[DailyUserSummaryRead]:
    """Defaults to the last 7 days (UTC) when no range is given. The range is clamped to
    ~3 months so one call cannot sweep an unbounded history."""
    today = utcnow().date()
    day_to = date_to or today
    day_from = date_from or (day_to - timedelta(days=6))
    if day_from > day_to:
        day_from = day_to
    if (day_to - day_from).days > _MAX_RANGE_DAYS:
        day_from = day_to - timedelta(days=_MAX_RANGE_DAYS)

    # Usernames are stored lower-cased (see WorkforceAggregator._to_sample); match the filter
    # the same way so a caller passing a different case still finds the rows.
    username = username.lower() if username else None
    rows = await WorkforceService(session).attendance(
        actor=actor, day_from=day_from, day_to=day_to,
        device_id=device_id, username=username,
    )
    await _audit_view(
        session, actor, target_type="workforce_attendance", target_id=username,
        detail={"from": str(day_from), "to": str(day_to),
                "device_id": str(device_id) if device_id else None, "username": username},
    )
    return rows


@router.get(
    "/teams/rollup",
    response_model=list[TeamRollupRead],
    summary="Attendance + productivity summed per team over a date range",
)
async def teams_rollup(
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> list[TeamRollupRead]:
    today = utcnow().date()
    day_to = date_to or today
    day_from = date_from or (day_to - timedelta(days=6))
    if day_from > day_to:
        day_from = day_to
    if (day_to - day_from).days > _MAX_RANGE_DAYS:
        day_from = day_to - timedelta(days=_MAX_RANGE_DAYS)

    rows = await WorkforceService(session).team_rollup(
        actor=actor, day_from=day_from, day_to=day_to)
    await _audit_view(
        session, actor, target_type="workforce_team_rollup", target_id=None,
        detail={"from": str(day_from), "to": str(day_to)},
    )
    return rows


@router.get(
    "/user",
    response_model=UserDetailRead,
    summary="One account's attendance + productivity + app breakdown over a date range",
)
async def user_detail(
    username: str = Query(...),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> UserDetailRead:
    today = utcnow().date()
    day_to = date_to or today
    day_from = date_from or (day_to - timedelta(days=6))
    if day_from > day_to:
        day_from = day_to
    if (day_to - day_from).days > _MAX_RANGE_DAYS:
        day_from = day_to - timedelta(days=_MAX_RANGE_DAYS)

    username = username.lower()   # stored lower-cased; match the same way
    detail = await WorkforceService(session).user_detail(
        actor=actor, username=username, day_from=day_from, day_to=day_to,
    )
    await _audit_view(
        session, actor, target_type="workforce_user", target_id=username,
        detail={"from": str(day_from), "to": str(day_to), "username": username},
    )
    return detail


@router.get(
    "/user/timeline",
    response_model=list[ActivitySegmentRead],
    summary="One account's app/website timeline for a single day (when each was used)",
)
async def user_timeline(
    username: str = Query(...),
    day: date = Query(...),
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> list[ActivitySegmentRead]:
    username = username.lower()   # stored lower-cased; match the same way
    segments = await WorkforceService(session).user_timeline(
        actor=actor, username=username, day=day,
    )
    await _audit_view(
        session, actor, target_type="workforce_timeline", target_id=username,
        detail={"day": str(day), "username": username},
    )
    return segments


@router.get(
    "/attendance/sessions",
    response_model=list[WorkSessionRead],
    summary="The work/break spans behind one account's day",
)
async def day_sessions(
    device_id: uuid.UUID = Query(...),
    username: str = Query(...),
    day: date = Query(...),
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> list[WorkSessionRead]:
    username = username.lower()   # stored lower-cased; match the same way
    spans = await WorkforceService(session).day_sessions(
        actor=actor, device_id=device_id, username=username, day=day,
    )
    await _audit_view(
        session, actor, target_type="workforce_sessions", target_id=username,
        detail={"device_id": str(device_id), "day": str(day), "username": username},
    )
    return spans


def _config(overrides: dict | None) -> CategoryConfigRead:
    """Build the config view: the buckets, the built-in defaults, and the org's overrides.
    `overrides` is the raw stored JSON (or None); CategoryOverrides re-validates it so a hand-
    edited or legacy value can never surface an invalid bucket to the UI."""
    stored = overrides or {}
    return CategoryConfigRead(
        buckets=list(BUCKETS),
        builtin=CategoryOverrides.model_validate(builtin_buckets()),
        overrides=CategoryOverrides.model_validate(
            {"domain": stored.get("domain") or {}, "app": stored.get("app") or {}}
        ),
    )


@router.get(
    "/categories",
    response_model=CategoryConfigRead,
    summary="The productivity taxonomy: built-in defaults and this org's overrides",
)
async def get_categories(
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> CategoryConfigRead:
    """Config, not employee data, so this is not a `workforce.view` row — but it is still
    gated on the entitlement (router dependency) and staff-only."""
    org = await session.get(Organization, actor.org_id)
    return _config(org.workforce_categories if org else None)


@router.put(
    "/categories",
    response_model=CategoryConfigRead,
    summary="Replace this org's productivity reclassification rules (admin only)",
)
async def put_categories(
    payload: CategoryOverrides,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> CategoryConfigRead:
    """Full replace — the body is the whole override set, so removing a rule is just leaving it
    out. Audited as a mutation (CLAUDE.md). The new rules apply from the next recompute of each
    reporting device; days already rolled up keep their buckets until their device next reports
    (or the nightly rebuild re-scores them)."""
    org = await session.get(Organization, actor.org_id)
    if org is None:
        raise NotFoundError("Organization not found")
    org.workforce_categories = payload.model_dump()
    await AuditService(session).record(
        org_id=actor.org_id,
        actor_id=actor.id,
        action="workforce.categories.update",
        target_type="organization",
        target_id=str(actor.org_id),
        detail={"domain_rules": len(payload.domain), "app_rules": len(payload.app),
                "domain": payload.domain, "app": payload.app},
    )
    await session.commit()
    return _config(org.workforce_categories)


# ── Department shifts ─────────────────────────────────────────────────────────


@router.get("/shifts", response_model=list[WorkShiftRead],
            summary="The org's department shifts")
async def list_shifts(
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> list[WorkShiftRead]:
    return await ShiftService(session).list_shifts(org_id=actor.org_id)


@router.post("/shifts", response_model=WorkShiftRead,
             status_code=status.HTTP_201_CREATED, summary="Create a department shift (admin)")
async def create_shift(
    body: WorkShiftWrite,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> WorkShiftRead:
    try:
        return await ShiftService(session).create_shift(actor=actor, body=body)
    except ConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))


@router.put("/shifts/{shift_id}", response_model=WorkShiftRead,
            summary="Update a department shift (admin)")
async def update_shift(
    shift_id: uuid.UUID,
    body: WorkShiftWrite,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> WorkShiftRead:
    try:
        return await ShiftService(session).update_shift(actor=actor, shift_id=shift_id, body=body)
    except ConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


@router.delete("/shifts/{shift_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Delete a shift — assigned teams are un-assigned, not deleted (admin)")
async def delete_shift(
    shift_id: uuid.UUID,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> None:
    try:
        await ShiftService(session).delete_shift(actor=actor, shift_id=shift_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


@router.get("/team-shifts", response_model=list[TeamShiftRead],
            summary="Each team with its assigned shift")
async def team_shifts(
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> list[TeamShiftRead]:
    return await ShiftService(session).list_team_assignments(org_id=actor.org_id)


@router.put("/teams/{team_id}/shift", response_model=TeamShiftRead,
            summary="Assign (or clear) the shift a team works (admin)")
async def assign_team_shift(
    team_id: uuid.UUID,
    body: ShiftAssignmentWrite,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> TeamShiftRead:
    try:
        return await ShiftService(session).assign_shift(actor=actor, team_id=team_id, body=body)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


# ── Account → directory-user mapping ──────────────────────────────────────────


@router.get("/accounts", response_model=list[TrackedAccountRead],
            summary="Tracked Windows accounts and the person each resolves to (from Assets)")
async def list_accounts(
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> list[TrackedAccountRead]:
    return await AccountService(session).list_accounts(org_id=actor.org_id)


# ── Attendance configuration (working days, thresholds, holidays) ─────────────


@router.get("/attendance-config", response_model=AttendanceConfigRead,
            summary="The org's attendance rules and holidays")
async def get_attendance_config(
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> AttendanceConfigRead:
    return await AttendanceConfigService(session).get_config(org_id=actor.org_id)


@router.put("/attendance-config", response_model=AttendanceConfigRead,
            summary="Set the working days and full/half-day thresholds (admin)")
async def put_attendance_config(
    body: AttendanceSettingsWrite,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> AttendanceConfigRead:
    return await AttendanceConfigService(session).set_settings(actor=actor, body=body)


@router.post("/holidays", response_model=HolidayRead,
             status_code=status.HTTP_201_CREATED, summary="Add a holiday (admin)")
async def add_holiday(
    body: HolidayWrite,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> HolidayRead:
    try:
        return await AttendanceConfigService(session).add_holiday(actor=actor, body=body)
    except ConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))


@router.delete("/holidays/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Remove a holiday (admin)")
async def delete_holiday(
    holiday_id: uuid.UUID,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> None:
    try:
        await AttendanceConfigService(session).delete_holiday(actor=actor, holiday_id=holiday_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
