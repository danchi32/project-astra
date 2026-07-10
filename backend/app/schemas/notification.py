import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import NotificationCategory, NotificationSeverity


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: NotificationCategory
    severity: NotificationSeverity
    title: str
    message: str
    link: str | None
    is_read: bool
    created_at: datetime

    @classmethod
    def from_model(cls, entry) -> "NotificationRead":
        return cls(
            id=entry.id,
            category=entry.category,
            severity=entry.severity,
            title=entry.title,
            message=entry.message,
            link=entry.link,
            is_read=entry.read_at is not None,
            created_at=entry.created_at,
        )


class UnreadCount(BaseModel):
    unread_count: int


class MarkAllReadResponse(BaseModel):
    marked: int
