import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import MessageRole


class ConversationCreate(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=200)


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: MessageRole
    content: str
    tool_trail: list[dict[str, Any]] | None
    created_at: datetime


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class SendMessageResponse(BaseModel):
    user_message: MessageRead
    assistant_message: MessageRead
