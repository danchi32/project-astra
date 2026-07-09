import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: str
    target_type: str
    target_id: str | None
    actor_id: uuid.UUID | None
    actor_email: str | None = None
    detail: dict[str, Any] | None
    created_at: datetime
