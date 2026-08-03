import uuid
from datetime import datetime
from typing import Literal

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

    # Learned articles only. Staff see these so that what the platform is teaching itself
    # is inspectable rather than invisible — including the ones not yet good enough to use.
    successes: int = 1
    failures: int = 0
    published_at: datetime | None = None
    # authored | learning | in_use | paused — decided server-side so the portal shows the
    # same judgement the search path acts on.
    learning_status: Literal["authored", "learning", "in_use", "paused"] = "authored"
