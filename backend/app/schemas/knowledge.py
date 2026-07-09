import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import KnowledgeSource


class KnowledgeArticleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=20000)


class KnowledgeArticleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    content: str
    source: KnowledgeSource
    created_at: datetime
