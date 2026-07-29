from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.database import get_db
from app.models import User, UserRole
from app.schemas.fleet import (
    BulkRemediateRequest,
    BulkRemediateResult,
    FleetIssuesResponse,
)
from app.services.fleet import FleetService

router = APIRouter(prefix="/fleet", tags=["fleet"])

staff_required = require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)


@router.get("/issues", response_model=FleetIssuesResponse, summary="Fleet-wide issues, ranked")
async def fleet_issues(
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> FleetIssuesResponse:
    issues = await FleetService(session).issues(org_id=actor.org_id)
    return FleetIssuesResponse(issues=issues)


@router.post("/remediate", response_model=BulkRemediateResult, summary="Push a fix to many devices")
async def fleet_remediate(
    body: BulkRemediateRequest,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> BulkRemediateResult:
    return await FleetService(session).bulk_remediate(
        actor=actor, device_ids=body.device_ids, action_id=body.action_id,
        params=body.params, reason=body.reason,
    )
