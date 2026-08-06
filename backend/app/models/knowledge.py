import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, JSON, String
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
    # Which vector space this embedding lives in. Vectors from different providers
    # are not comparable, and cosine similarity reports a mismatch as 0.0 rather
    # than an error — so search filters on this instead of meeting the problem as
    # silence.
    embedding_model: Mapped[str] = mapped_column(
        String(60), nullable=False, default="hash-256", index=True
    )
    source: Mapped[KnowledgeSource] = mapped_column(
        Enum(KnowledgeSource, native_enum=False, length=20,
             values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=KnowledgeSource.MANUAL,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)

    # ── Learned articles ───────────────────────────────────────────────────
    # The topic a learned article documents, and the key that decides whether a confirmed
    # fix updates an existing article or starts a new one. Usually a remediation action id
    # ("restart_outlook"); for actions that take a target it carries the discriminator too
    # ("restart_application:chrome"), because restarting Chrome and restarting Notepad are
    # not the same runbook. NULL on everything a human wrote.
    action_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    # The user phrasings that led here. Kept verbatim (redacted) rather than summarised:
    # retrieval matches the words a person actually types, so the next user who says
    # "outlook stuck again" needs those words to be in the article.
    symptom_samples: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    # Evidence, and the reason an article can lose its place: a fix that worked eleven
    # times and has now failed four is no longer something to recommend confidently.
    successes: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # NULL means a candidate: recorded, visible to staff, but NOT returned by search.
    # One success is an anecdote — publishing it would bury hand-written runbooks under
    # a stream of near-identical entries.
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    @property
    def learning_status(self) -> str:
        """How this article stands, resolved here so the portal never re-derives the rule.

        "authored"  — a person wrote it; none of the below applies.
        "learning"  — recorded, not yet confirmed often enough to be used.
        "in_use"    — searchable, and the assistant may answer from it.
        "paused"    — was in use, but has failed too often to keep recommending.
        """
        from app.services.ai.learning import is_recommendable

        if self.source is not KnowledgeSource.RESOLVED_ISSUE:
            return "authored"
        if self.published_at is None:
            return "learning"
        return "in_use" if is_recommendable(self) else "paused"
