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
    # E8: until then the extension only records (mode "log"). Set when the org first saves a
    # policy; NULL for policies from before the pilot existed. An admin can end it early.
    pilot_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # D1: the hosts of `policy.blocked_categories` as they were when it was saved, served to PCs
    # beside `blocked_sites`. A copy, so a changed list reaches a PC only with a new version.
    category_hosts: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


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
    # D7: the person's answer to a warn / justify prompt, and the reason code they picked.
    outcome: Mapped[str | None] = mapped_column(String(10), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(20), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class GuardDiscovery(Base):
    """Phase 3 · D5: a PC's latest map of where sensitive files are, by folder, in counts.
    One row per device, replaced by each weekly scan. `folders` holds only folders where
    something was found: path, files read, files with findings, counts per kind, contact
    lists. No file names, no content."""

    __tablename__ = "guard_discoveries"

    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    files_scanned: Mapped[int] = mapped_column(Integer, nullable=False)
    files_skipped: Mapped[int] = mapped_column(Integer, nullable=False)
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    folders: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class GuardSuggestionDismissal(Base):
    """Phase 3 · D5: a policy suggestion an admin chose not to take. It stays hidden for good."""

    __tablename__ = "guard_suggestion_dismissals"

    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    dismissed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    dismissed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class GuardApproval(Base):
    """Phase 3 · D7: a person asked IT to let one thing through: one Windows account, one PC,
    one site, one channel (paste / drop / file / submit). An admin approves it for a set time
    or denies it. What was found is kept as counts, as on the event. Never the content.

    status: pending → approved | denied. An approval stops counting at `valid_until`; a
    pending request older than a day is shown as expired and cannot be approved."""

    __tablename__ = "guard_approvals"
    __table_args__ = (Index("ix_guard_approvals_org_status", "org_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    windows_user: Mapped[str] = mapped_column(String(256), nullable=False)
    site: Mapped[str] = mapped_column(String(253), nullable=False)
    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    counts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    contact_list: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    keyword_hits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
