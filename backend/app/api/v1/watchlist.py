"""N2 · Watchlist (staff): what has gone quiet, is running out, or never finished. Read-only."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.database import get_db
from app.models import User, UserRole
from app.services import watchlist

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class SilentPc(BaseModel):
    device_id: uuid.UUID
    hostname: str
    last_seen_at: datetime | None
    hours: int


class WarrantyEnding(BaseModel):
    asset_id: uuid.UUID
    name: str
    ends: str
    days_left: int
    bucket: str  # expired | 30 | 60 | 90


class StuckWork(BaseModel):
    task_id: uuid.UUID
    action: str
    hostname: str | None
    rollout: str | None
    state: str
    hours: int


class AgentBehind(BaseModel):
    hostname: str
    version: str


class Watchlist(BaseModel):
    silent_hours: int
    silent: list[SilentPc]
    warranty: list[WarrantyEnding]
    stuck: list[StuckWork]
    latest_agent: str | None   # None = no update channel configured, so nothing to compare
    agents_behind: list[AgentBehind]


@router.get("", response_model=Watchlist,
            summary="PCs gone quiet, warranties ending, work never finished, agents behind (staff)")
async def get_watchlist(
    silent_hours: int = Query(default=6, ge=1, le=24 * 30),
    actor: User = Depends(require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)),
    session: AsyncSession = Depends(get_db),
) -> Watchlist:
    return Watchlist(**await watchlist.build(session, org_id=actor.org_id, silent_hours=silent_hours))
