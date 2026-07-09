import uuid

from sqlalchemy import Integer, String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin


class SemanticCacheEntry(TimestampMixin, Base):
    """A verified general-knowledge answer keyed by its query embedding, so a repeated
    or near-duplicate question can be served without another LLM call."""

    __tablename__ = "semantic_cache_entries"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)
    query_text: Mapped[str] = mapped_column(String(1000), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    answer: Mapped[str] = mapped_column(String(10000), nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
