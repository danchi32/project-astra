"""Phase 3 · AI Smart Guard: the org's browser policy (D10/D1/D2) and each PC's status.

Behind the `ai_guard` entitlement, which no plan includes: an operator turns it on per
organization. Editing is admin-only and audited. Staff can read the status.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles, requires
from app.core.database import get_db
from app.models import User, UserRole
from app.services import browser_policy
from app.services.browser_policy import BrowserPolicyBody, BrowserResult
from app.services.entitlements import AI_GUARD

router = APIRouter(prefix="/guard", tags=["guard"], dependencies=[Depends(requires(AI_GUARD))])


class BrowserPolicyRead(BaseModel):
    version: int
    policy: BrowserPolicyBody
    updated_at: datetime | None


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
        return BrowserPolicyRead(version=0, policy=BrowserPolicyBody(), updated_at=None)
    return BrowserPolicyRead(version=row.version, policy=BrowserPolicyBody(**row.policy), updated_at=row.updated_at)


@router.put("/browser-policy", response_model=BrowserPolicyRead,
            summary="Set the organization's browser policy (admin; audited)")
async def put_browser_policy(
    body: BrowserPolicyBody,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> BrowserPolicyRead:
    row = await browser_policy.put(session, actor=actor, body=body)
    return BrowserPolicyRead(version=row.version, policy=BrowserPolicyBody(**row.policy), updated_at=row.updated_at)


@router.get("/browser-policy/devices", response_model=list[DeviceBrowserState],
            summary="What each PC last reported after applying the policy (staff)")
async def browser_policy_devices(
    actor: User = Depends(require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)),
    session: AsyncSession = Depends(get_db),
) -> list[DeviceBrowserState]:
    return [DeviceBrowserState(device_id=s.device_id, hostname=host, version=s.version,
                               results=[BrowserResult(**r) for r in s.results], reported_at=s.reported_at)
            for s, host in await browser_policy.device_states(session, actor.org_id)]
