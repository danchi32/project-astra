import uuid

from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin


class LearnedAction(TimestampMixin, Base):
    """A fix the AI applied for an issue the built-in rules couldn't classify,
    remembered by its query embedding so the SAME kind of issue is resolved next
    time by the built-in path — no further LLM call. This is how the assistant's
    'common issue' coverage grows over time, per organization."""

    __tablename__ = "learned_actions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)
    query_text: Mapped[str] = mapped_column(String(1000), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    # The remediation to apply (must be an action in the allowlist) and its params.
    action_id: Mapped[str] = mapped_column(String(64), nullable=False)
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
