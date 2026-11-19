import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, utcnow


class AuditPack(Base):
    """Phase 3b · I4: a client's security questionnaire and SAVIO's draft answers.

    `rows` is a list of {"n", "question", "status": pending | answered | gap, "answer",
    "evidence": [evidence keys], "edited_by"}. The questions came from an uploaded file and are
    untrusted text; the answers are a model's draft from SAVIO's own evidence until a person
    edits or accepts them. The uploaded file itself is not kept."""

    __tablename__ = "audit_packs"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="answering")   # answering | ready | failed
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    rows: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
