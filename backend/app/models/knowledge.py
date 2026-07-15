import enum
import uuid

from sqlalchemy import Enum, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin


class KnowledgeSource(str, enum.Enum):
    MANUAL = "manual"                # authored by IT staff
    RESOLVED_ISSUE = "resolved_issue"  # captured from a confirmed fix (the "learns daily" path)


class KnowledgeArticle(TimestampMixin, Base):
    """An org knowledge-base article (runbook, how-to, known fix). The embedding of
    title+content lets the AI retrieve relevant articles to ground its answers."""

    __tablename__ = "knowledge_articles"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    # NULL org_id = a GLOBAL article curated by the platform operator, searchable by
    # EVERY organization's assistant (in addition to that org's own articles).
    org_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(String(20000), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    source: Mapped[KnowledgeSource] = mapped_column(
        Enum(KnowledgeSource, native_enum=False, length=20,
             values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=KnowledgeSource.MANUAL,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
