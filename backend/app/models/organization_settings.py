import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin, utcnow


class OrganizationSettings(TimestampMixin, Base):
    """Per-organization policy, one row per org (created lazily on first read).

    Every field here is enforced somewhere in the backend — this is operational
    policy, not decoration:
      - auto_approve_automatic       → RemediationService.create_task
      - require_admin_for_approval   → RemediationService.approve_task
      - min_password_length          → UserService.create_user + change-password
      - enrollment_token_default_days→ DeviceService.create_enrollment_token
    """

    __tablename__ = "organization_settings"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True,
    )

    # Automation kill-switch: when False, even automatic-tier remediations wait for
    # a human. Lets an org pause all self-healing without touching the tier table.
    auto_approve_automatic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # When True, approval_required actions can only be cleared by an admin (a
    # technician alone is not enough). Admin-only tier is unaffected — always admin.
    require_admin_for_approval_tier: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Security baseline. The absolute floor of 12 is still enforced in schemas; this
    # value may raise it, never lower it.
    min_password_length: Mapped[int] = mapped_column(Integer, nullable=False, default=12)

    # Default lifetime applied to new enrollment tokens when the request omits one.
    enrollment_token_default_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
