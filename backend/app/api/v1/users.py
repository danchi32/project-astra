import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.database import get_db
from app.models import User, UserRole
from app.repositories.users import UserRepository
from app.schemas.pagination import DEFAULT_PAGE_SIZE, Page, build, clamp
from app.schemas.users import UserCreate, UserRead, UserUpdate
from app.services.users import UserService

router = APIRouter(prefix="/users", tags=["users"])

staff_required = require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)
admin_required = require_roles(UserRole.ADMIN)


@router.get("", response_model=Page[UserRead], summary="List users in your organization")
async def list_users(
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> Page[UserRead]:
    page, page_size = clamp(page, page_size)
    rows, total = await UserRepository(session).list_page(
        actor.org_id, offset=(page - 1) * page_size, limit=page_size
    )
    # Converted here rather than leaning on FastAPI's response_model coercion:
    # a generic Page[...] is built before that step, so a SQLAlchemy row would
    # reach pydantic unvalidated and fail at import time.
    return build([UserRead.model_validate(u) for u in rows], total, page, page_size)


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
