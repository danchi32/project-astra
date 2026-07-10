import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification, NotificationCategory, NotificationSeverity, User
from app.models.base import utcnow
from app.repositories.notifications import NotificationRepository
from app.schemas.notification import NotificationRead
from app.services.exceptions import NotFoundError


class NotificationService:
    """Called both by other services (to raise an alert) and by the notifications API
    (to read/dismiss them). `notify()` adds but does not commit — the caller's existing
    transaction commits once, same convention as AuditService.record()."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = NotificationRepository(session)

    async def notify(
        self,
        *,
        org_id: uuid.UUID,
        category: NotificationCategory,
        severity: NotificationSeverity,
        title: str,
        message: str,
        link: str | None = None,
    ) -> Notification:
        return await self.repo.add(
            Notification(
                org_id=org_id,
                category=category,
                severity=severity,
                title=title,
                message=message,
                link=link,
            )
        )

    async def list_for_org(
        self, *, actor: User, unread_only: bool = False, limit: int = 100
    ) -> list[NotificationRead]:
        entries = await self.repo.list_by_org(actor.org_id, unread_only=unread_only, limit=limit)
        return [NotificationRead.from_model(e) for e in entries]

    async def unread_count(self, *, actor: User) -> int:
        return await self.repo.count_unread(actor.org_id)

    async def mark_read(self, *, actor: User, notification_id: uuid.UUID) -> NotificationRead:
        entry = await self.repo.get(notification_id)
        if entry is None or entry.org_id != actor.org_id:
            raise NotFoundError("Notification not found")
        if entry.read_at is None:
            entry.read_at = utcnow()
            await self.session.commit()
        return NotificationRead.from_model(entry)

    async def mark_all_read(self, *, actor: User) -> int:
        marked = await self.repo.mark_all_read(actor.org_id, read_at=utcnow())
        await self.session.commit()
        return marked
