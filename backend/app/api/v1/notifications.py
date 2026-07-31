import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.notification import MarkAllReadResponse, NotificationRead, UnreadCount
from app.schemas.pagination import DEFAULT_PAGE_SIZE, Page, build, clamp
from app.services.notifications import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=Page[NotificationRead], summary="List notifications")
async def list_notifications(
    unread_only: bool = Query(default=False),
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Page[NotificationRead]:
    page, page_size = clamp(page, page_size)
    items, total = await NotificationService(session).list_page(
        actor=actor, unread_only=unread_only, offset=(page - 1) * page_size, limit=page_size
    )
    return build(items, total, page, page_size)


@router.get("/unread-count", response_model=UnreadCount, summary="Unread notification count")
async def unread_count(
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UnreadCount:
    count = await NotificationService(session).unread_count(actor=actor)
    return UnreadCount(unread_count=count)


@router.post("/{notification_id}/read", response_model=NotificationRead, summary="Mark one notification read")
async def mark_read(
    notification_id: uuid.UUID,
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> NotificationRead:
    return await NotificationService(session).mark_read(actor=actor, notification_id=notification_id)


@router.post("/read-all", response_model=MarkAllReadResponse, summary="Mark all notifications read")
async def mark_all_read(
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MarkAllReadResponse:
    marked = await NotificationService(session).mark_all_read(actor=actor)
    return MarkAllReadResponse(marked=marked)
