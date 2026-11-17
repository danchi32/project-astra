import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin, utcnow


class OrgBrowserPolicy(TimestampMixin, Base):
    """Phase 3 · D10: the browser lock-down an organization asks its PCs to apply.

    One row per org. `policy` is the browser-neutral shape the agent's `BrowserPolicy` reads.
    `version` goes up on every change, so a device's report says which one it applied. Only
    served to PCs of an org holding the `ai_guard` entitlement; any other org's PCs get an
    empty policy, which makes them remove what SAVIO set."""

    __tablename__ = "org_browser_policies"

    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    policy: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class DeviceBrowserPolicyState(Base):
    """What a device last reported after applying the policy: per browser, what it set,
    repaired (drift), removed, could not set because another policy owns it (conflicts), and
    any error. One row per device, replaced on each report."""

    __tablename__ = "device_browser_policy_states"

    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    results: Mapped[list] = mapped_column(JSON, nullable=False)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class GuardEvent(Base):
    """Phase 3 · E3: one thing the browser extension saw on a PC.

    Counts and flags only, in the agent's fixed schema: the site's host name, how it left the
    page (paste, drop, file, submit), the org's mode and the decision, how many of each kind
    were found. Never the text, not even a fragment. `windows_user` is the account Windows
    reported to the agent, not anything the browser said."""

    __tablename__ = "guard_events"
    __table_args__ = (Index("ix_guard_events_org_occurred", "org_id", "occurred_at"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    windows_user: Mapped[str] = mapped_column(String(256), nullable=False)
    site: Mapped[str] = mapped_column(String(253), nullable=False)
    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    mode: Mapped[str] = mapped_column(String(10), nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    counts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    contact_list: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    keyword_hits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unknown: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
