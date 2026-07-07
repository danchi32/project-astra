import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.database import get_db
from app.models import User, UserRole
from app.schemas.users import UserCreate, UserRead, UserUpdate
from app.services.users import UserService

router = APIRouter(prefix="/users", tags=["users"])

staff_required = require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)
admin_required = require_roles(UserRole.ADMIN)


@router.get("", response_model=list[UserRead], summary="List users in your organization")
async def list_users(
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> list[User]:
    return await UserService(session).list_users(actor=actor)


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user (admin only)",
)
async def create_user(
    body: UserCreate,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> User:
    return await UserService(session).create_user(actor=actor, data=body)


@router.get("/{user_id}", response_model=UserRead, summary="Get a user in your organization")
async def get_user(
    user_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> User:
    return await UserService(session).get_user(actor=actor, user_id=user_id)


@router.patch("/{user_id}", response_model=UserRead, summary="Update a user (admin only)")
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> User:
    return await UserService(session).update_user(actor=actor, user_id=user_id, data=body)


@router.delete(
    "/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a user (admin only)"
)
async def delete_user(
    user_id: uuid.UUID,
    actor: User = Depends(admin_required),
    session: AsyncSession = Depends(get_db),
) -> None:
    await UserService(session).delete_user(actor=actor, user_id=user_id)
