"""J2 · Recommendations (staff). Read refreshes them from live data; dismiss / restore are audited."""
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.database import get_db
from app.models import User, UserRole
from app.services.recommendations import RecommendationService

router = APIRouter(prefix="/recommendations", tags=["recommendations"])
staff_required = require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)


class RecommendationRead(BaseModel):
    id: uuid.UUID
    key: str
    title: str
    evidence: dict
    risk: str
    effort: str
    action_id: str | None
    advice: str
    status: str
    time_minutes: int | None
    # Only when the org has set an hourly IT cost. `basis` says how both were worked out.
    inr: int | None
    basis: str | None
    dismissed_reason: str | None
    dismissed_at: datetime | None
    created_at: datetime


class DismissRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


def _read(rec, cost: int | None) -> RecommendationRead:
    count = (rec.evidence or {}).get("count", 0)
    inr = round(rec.time_minutes / 60 * cost) if cost and rec.time_minutes else None
    basis = None
    if rec.time_minutes:
        per = rec.time_minutes // count if count else rec.time_minutes
        basis = f"{count} PC{'s' if count != 1 else ''} x {per} min by hand"
        if inr is not None:
            basis += f" x ₹{cost}/hour"
    return RecommendationRead(
        id=rec.id, key=rec.key, title=rec.title, evidence=rec.evidence, risk=rec.risk,
        effort=rec.effort, action_id=rec.action_id, advice=rec.advice, status=rec.status,
        time_minutes=rec.time_minutes, inr=inr, basis=basis,
        dismissed_reason=rec.dismissed_reason, dismissed_at=rec.dismissed_at,
        created_at=rec.created_at,
    )


@router.get("", response_model=list[RecommendationRead],
            summary="What SAVIO recommends, refreshed from live data, riskiest first (staff)")
async def list_recommendations(
    status: Literal["open", "dismissed", "resolved"] = Query(default="open"),
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> list[RecommendationRead]:
    rows, cost = await RecommendationService(session).list(actor=actor, status=status)
    return [_read(r, cost) for r in rows]


@router.post("/{rec_id}/dismiss", response_model=RecommendationRead,
             summary="Dismiss a recommendation with a reason (staff; audited)")
async def dismiss_recommendation(
    rec_id: uuid.UUID, body: DismissRequest,
    actor: User = Depends(staff_required), session: AsyncSession = Depends(get_db),
) -> RecommendationRead:
    rec = await RecommendationService(session).dismiss(actor=actor, rec_id=rec_id, reason=body.reason)
    return _read(rec, None)


@router.post("/{rec_id}/restore", response_model=RecommendationRead,
             summary="Bring back a dismissed recommendation (staff; audited)")
async def restore_recommendation(
    rec_id: uuid.UUID,
    actor: User = Depends(staff_required), session: AsyncSession = Depends(get_db),
) -> RecommendationRead:
    rec = await RecommendationService(session).restore(actor=actor, rec_id=rec_id)
    return _read(rec, None)
