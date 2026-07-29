import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin


class BannedSoftware(TimestampMixin, Base):
    """An org's restricted/banned application. A device fails the 'no banned software'
    compliance check when any installed app name contains `pattern` (case-insensitive).
    Detection only — nothing is uninstalled automatically."""

    __tablename__ = "banned_software"
    __table_args__ = (
        UniqueConstraint("org_id", "pattern", name="uq_banned_software_org_pattern"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Human-facing label (e.g. "uTorrent").
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Lower-cased substring matched against installed-app names.
    pattern: Mapped[str] = mapped_column(String(120), nullable=False)
