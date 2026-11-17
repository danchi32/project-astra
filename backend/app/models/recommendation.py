import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin


class Recommendation(TimestampMixin, Base):
    """J2: one thing SAVIO suggests the org do, with the evidence for it.

    Rebuilt from live data whenever the list is read (`RecommendationService.refresh`). A row
    exists so a dismissal sticks: `key` names the finding ("check:firewall",
    "warranty:<asset id>"), and a dismissed key stays dismissed while the finding lasts.
    A finding that clears is marked resolved; if it comes back later, it reopens.
    """

    __tablename__ = "recommendations"
    __table_args__ = (UniqueConstraint("org_id", "key", name="uq_recommendations_org_key"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # {"devices": [...], "count": n, "detail": "..."}: what was seen, named.
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False)
    risk: Mapped[str] = mapped_column(String(10), nullable=False)          # high | medium | low
    effort: Mapped[str] = mapped_column(String(20), nullable=False)        # one_click | manual | purchase
    # Minutes of IT work the fix takes by hand, and the basis for it, e.g. "3 PCs x 15 min".
    time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    advice: Mapped[str] = mapped_column(String(600), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="open")  # open | dismissed | resolved
    dismissed_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    dismissed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
