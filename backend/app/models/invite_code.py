import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin


class InviteCode(TimestampMixin, Base):
    """A single-use code that authorizes creating ONE new organization. The platform
    operator issues codes (scripts/create_invite.py); registration consumes one.
    This is what makes org creation invite-only rather than open self-service.

    Only the hash is stored — the raw code is shown once at creation, like an
    enrollment token."""

    __tablename__ = "invite_codes"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    code_hash: Mapped[str] = mapped_column(unique=True, index=True, nullable=False)
    note: Mapped[str | None] = mapped_column(nullable=True)  # e.g. the customer name
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Set when consumed — a code enrolls exactly one organization, then is spent.
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    used_by_org_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
