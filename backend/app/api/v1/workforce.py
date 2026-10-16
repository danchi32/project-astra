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

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles, requires
from app.core.database import get_db
from app.models import User, UserRole
from app.models.base import utcnow
from app.schemas.workforce import DailyUserSummaryRead, UserDetailRead, WorkSessionRead
from app.services.audit import AuditService
from app.services.entitlements import WORKFORCE_INSIGHTS
from app.services.workforce import WorkforceService

router = APIRouter(
    prefix="/tracker",
    tags=["workforce insights"],
    dependencies=[Depends(requires(WORKFORCE_INSIGHTS))],
)

staff_required = require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)

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
