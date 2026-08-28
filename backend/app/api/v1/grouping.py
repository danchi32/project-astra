import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import User, UserRole
from app.schemas.grouping import (
    DeviceGroupRead,
    GroupWrite,
    MembershipWrite,
    TeamMembershipWrite,
    UserTeamRead,
)
from app.services.exceptions import ConflictError, NotFoundError
from app.services.grouping import GroupingService

router = APIRouter(prefix="/grouping", tags=["groups & teams"])

# Reading the group list is open to anyone signed in — it is a filter dropdown on pages
# they already have, and hiding the names of the groups while showing their contents would
# be theatre. Changing them is staff work.
staff_required = require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)


def _handle(exc: Exception) -> HTTPException:
    if isinstance(exc, ConflictError):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    if isinstance(exc, NotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    return HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


# ── Device groups ──────────────────────────────────────────────────────────

@router.get("/groups", response_model=list[DeviceGroupRead],
            summary="List the org's device groups")
async def list_groups(
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[DeviceGroupRead]:
    return await GroupingService(session).list_groups(org_id=actor.org_id)


@router.post("/groups", response_model=DeviceGroupRead,
             status_code=status.HTTP_201_CREATED, summary="Create a device group")
async def create_group(
    body: GroupWrite,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> DeviceGroupRead:
    try:
        return await GroupingService(session).create_group(actor=actor, body=body)
    except (ValueError, ConflictError) as exc:
        raise _handle(exc)


@router.patch("/groups/{group_id}", response_model=DeviceGroupRead,
              summary="Rename or restyle a device group")
async def update_group(
    group_id: uuid.UUID,
    body: GroupWrite,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> DeviceGroupRead:
    try:
        return await GroupingService(session).update_group(
            actor=actor, group_id=group_id, body=body
        )
    except (ValueError, ConflictError, NotFoundError) as exc:
        raise _handle(exc)


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Delete a device group (the devices are untouched)")
async def delete_group(
    group_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> None:
    try:
        await GroupingService(session).delete_group(actor=actor, group_id=group_id)
    except NotFoundError as exc:
        raise _handle(exc)


@router.get("/groups/{group_id}/devices", response_model=list[uuid.UUID],
            summary="Device ids in a group")
async def group_members(
    group_id: uuid.UUID,
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[uuid.UUID]:
    try:
        return await GroupingService(session).group_member_ids(
            org_id=actor.org_id, group_id=group_id
        )
    except NotFoundError as exc:
        raise _handle(exc)


@router.put("/groups/{group_id}/devices", response_model=DeviceGroupRead,
            summary="Replace a group's devices with this exact set")
async def set_group_members(
    group_id: uuid.UUID,
    body: MembershipWrite,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> DeviceGroupRead:
    service = GroupingService(session)
    try:
        await service.set_group_members(
            actor=actor, group_id=group_id, device_ids=body.device_ids
        )
    except NotFoundError as exc:
        raise _handle(exc)
    groups = await service.list_groups(org_id=actor.org_id)
    return next(g for g in groups if g.id == group_id)


# ── User teams ─────────────────────────────────────────────────────────────

@router.get("/teams", response_model=list[UserTeamRead], summary="List the org's teams")
async def list_teams(
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[UserTeamRead]:
    return await GroupingService(session).list_teams(org_id=actor.org_id)


@router.post("/teams", response_model=UserTeamRead,
             status_code=status.HTTP_201_CREATED, summary="Create a team")
async def create_team(
    body: GroupWrite,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> UserTeamRead:
    try:
        return await GroupingService(session).create_team(actor=actor, body=body)
    except (ValueError, ConflictError) as exc:
        raise _handle(exc)


@router.patch("/teams/{team_id}", response_model=UserTeamRead,
              summary="Rename or restyle a team")
async def update_team(
    team_id: uuid.UUID,
    body: GroupWrite,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> UserTeamRead:
    try:
        return await GroupingService(session).update_team(
            actor=actor, team_id=team_id, body=body
        )
    except (ValueError, ConflictError, NotFoundError) as exc:
        raise _handle(exc)


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Delete a team (the users are untouched)")
async def delete_team(
    team_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> None:
    try:
        await GroupingService(session).delete_team(actor=actor, team_id=team_id)
    except NotFoundError as exc:
        raise _handle(exc)


@router.get("/teams/{team_id}/users", response_model=list[uuid.UUID],
            summary="User ids in a team")
async def team_members(
    team_id: uuid.UUID,
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[uuid.UUID]:
    try:
        return await GroupingService(session).team_member_ids(
            org_id=actor.org_id, team_id=team_id
        )
    except NotFoundError as exc:
        raise _handle(exc)


@router.put("/teams/{team_id}/users", response_model=UserTeamRead,
            summary="Replace a team's members with this exact set")
async def set_team_members(
    team_id: uuid.UUID,
    body: TeamMembershipWrite,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> UserTeamRead:
    service = GroupingService(session)
    try:
        await service.set_team_members(
            actor=actor, team_id=team_id, user_ids=body.user_ids
        )
    except NotFoundError as exc:
        raise _handle(exc)
    teams = await service.list_teams(org_id=actor.org_id)
    return next(t for t in teams if t.id == team_id)
