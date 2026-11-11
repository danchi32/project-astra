"""L1 — Free IT Health Check report (every plan and the trial; staff only)."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.database import get_db
from app.models import User, UserRole
from app.services import health_check

router = APIRouter(prefix="/reports", tags=["reports"])
staff_required = require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)


@router.get("/health-check", summary="IT Health Check: the fleet's problems, ranked, from collected data")
async def get_health_check(
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> dict:
    return await health_check.build(session, actor.org_id)
