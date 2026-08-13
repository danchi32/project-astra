from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles, requires
from app.core.database import get_db
from app.models import User, UserRole
from app.schemas.fleet import (
    BulkRemediateRequest,
    BulkRemediateResult,
    FleetIssuesResponse,
)
from app.services.entitlements import FLEET_CORRELATION
from app.services.fleet import FleetService

# Expert-tier: cross-device correlation and one-click mass remediation.
router = APIRouter(
    prefix="/fleet", tags=["fleet"],
    dependencies=[Depends(requires(FLEET_CORRELATION))],
)

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


# Admin only: uninstall/USB-block-tier work needs an admin approver, and this closes or
# reopens a port across the whole fleet in one call. The tier check inside create_task is
# the real boundary; requiring admin here refuses the batch before it starts rather than
# after every device has failed the per-device check.
admin_required = require_roles(UserRole.ADMIN)


@router.post("/usb/{state}", response_model=BulkRemediateResult,
             summary="Block or allow USB storage on every device")
async def fleet_usb(
    state: str,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> BulkRemediateResult:
    if state not in ("block", "allow"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Use /fleet/usb/block or /fleet/usb/allow.")
    return await FleetService(session).usb_on_all(actor=actor, block=state == "block")
