"""Workforce Insights ("Tracker") — attendance, presence and (later) productivity.

Three tables, in the shape the plan lays out (docs/WORKFORCE_INSIGHTS_PLAN.md §2.2):

    activity_samples   raw presence events the agent pushes, retention-limited
        ↓ aggregation (per device, per day — mirrors telemetry's roll_up_snapshot)
    work_sessions      derived spans: a person signed in and present
        ↓
    daily_user_summary one row per (device, Windows account, day): first-in, last-out, worked

Keyed on the Windows ACCOUNT the agent reports, not on an ASTRA portal user — those are the
IT staff who sign in to the portal, not the people being tracked, and there is no employee
identity in the product yet. So the natural, zero-config unit is (device, username): it is
exactly what the agent already enumerates, and the "Tracker → Users" list is just the
distinct accounts seen. `daily_user_summary.user_id` is the reserved hook for later resolving
an account to a directory user (naming, manager, self-view) — nullable, filled by enrichment,
never required to show attendance.

Phase 1 fills attendance only (first-in / last-out / worked). The active/idle columns (P2)
and productive/neutral/unproductive columns (P3) exist here so those phases add data, not
migrations; they stay NULL until their collector ships, which is why they are nullable rather
than defaulted to a misleading 0.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin, utcnow

# Presence events the agent reports. Split into the two that matter to aggregation: those
# that mean "a person is at the machine, working" and those that mean "they stepped away".
# A work span opens on a PRESENT event and closes on an AWAY one. P1 emits the session
# events (logon/logoff/lock/unlock); P2 adds active/idle from GetLastInputInfo.
ACTIVITY_LOGON = "logon"
ACTIVITY_LOGOFF = "logoff"
ACTIVITY_LOCK = "lock"
ACTIVITY_UNLOCK = "unlock"
ACTIVITY_ACTIVE = "active"   # input resumed after an idle gap (P2)
ACTIVITY_IDLE = "idle"       # no input past the threshold (P2)
ACTIVITY_FOREGROUND = "foreground"  # a periodic sample of the active app/website (P3)

ACTIVITY_KINDS = frozenset({
    ACTIVITY_LOGON, ACTIVITY_LOGOFF, ACTIVITY_LOCK, ACTIVITY_UNLOCK,
    ACTIVITY_ACTIVE, ACTIVITY_IDLE, ACTIVITY_FOREGROUND,
})
#: Events that mean the person is present and the clock should be running.
ACTIVITY_PRESENT = frozenset({ACTIVITY_LOGON, ACTIVITY_UNLOCK, ACTIVITY_ACTIVE})
#: Events that mean the person has stepped away and a work span should close.
ACTIVITY_AWAY = frozenset({ACTIVITY_LOGOFF, ACTIVITY_LOCK, ACTIVITY_IDLE})

# Derived span kinds. P1 writes only "work"; the discriminator is here so P2's break/idle
# timeline is a read against this table, not a schema change.
SPAN_WORK = "work"
SPAN_BREAK = "break"


class ActivitySample(TimestampMixin, Base):
    """One presence event from the agent, raw and retention-limited.

    Rows are append-only (an event happened at a moment), unlike the point-in-time
    `device_sessions` table which is replaced wholesale each push. Attendance needs the
    history of transitions over the day, which that table deliberately does not keep.
    """

    __tablename__ = "activity_samples"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)

    # DOMAIN\user as the session's token reports it. Non-null: an event with no user
    # attached (the logon screen, an unassigned listener) is not attributable attendance
    # and the agent simply does not send it.
    username: Mapped[str] = mapped_column(String(150), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    # Windows session id the event belongs to, when known — lets aggregation keep two
    # concurrent accounts on one machine (a shared/terminal box) from blurring together.
    session_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # Only for kind == "foreground" (P3 productivity): the active app's process/display name
    # and, for a browser, the website domain. Domain only — never a path or query string
    # (that is where tokens and private parameters live; see plan §6). Null for session events.
    app: Mapped[str | None] = mapped_column(String(260), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)


class WorkSession(TimestampMixin, Base):
    """A derived span during which one account was signed in and present on one device.

    Recomputed from `activity_samples`, never written directly by the agent. Replaced per
    (device, day) on each aggregation, so it is a projection of the raw events and cannot
    drift from them. A span that crosses midnight is split at the UTC day boundary into one
    row per day, which keeps the `day` key — and the per-day replace — clean.
    """

    __tablename__ = "work_sessions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)

    username: Mapped[str] = mapped_column(String(150), nullable=False)
    # UTC calendar day this span is counted against. Indexed with device because aggregation
    # and every read work one (device, day) at a time.
    day: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(10), nullable=False, default=SPAN_WORK)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # NULL only for a span still open at the end of the data — i.e. someone presently at the
    # machine today. A past day is always closed by aggregation.
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DailyUserSummary(TimestampMixin, Base):
    """One row per (device, Windows account, day): the attendance headline.

    The durable history — `activity_samples` are pruned after a short window, these are not.
    """

    __tablename__ = "daily_user_summary"
    __table_args__ = (
        UniqueConstraint("device_id", "username", "day", name="uq_daily_user_summary_dev_user_day"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)

    username: Mapped[str] = mapped_column(String(150), nullable=False)
    # The reserved hook for resolving this Windows account to a directory user later
    # (naming, manager assignment, employee self-view). SET NULL on user delete: losing the
    # link must never delete the attendance. Nullable and unused in P1.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    day: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    first_in: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_out: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    worked_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # P2 (GetLastInputInfo): real at-keyboard time vs auto-break. NULL until that collector
    # ships — a 0 here would read as "present all day, never touched the keyboard", which is
    # a claim P1 cannot make.
    active_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    idle_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # P3 (foreground app/website + category engine). NULL until then, for the same reason.
    productive_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    neutral_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unproductive_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class DailyAppUsage(TimestampMixin, Base):
    """Minutes one account spent in one app/website on one day, with its productivity bucket.

    The breakdown behind a day's productive/neutral/unproductive split, and what the per-user
    detail view lists as "top apps / sites". Recomputed with the daily summary (replaced per
    device-day), so it is a projection of the raw foreground samples and cannot drift."""

    __tablename__ = "daily_app_usage"
    __table_args__ = (
        UniqueConstraint("device_id", "username", "day", "label",
                         name="uq_daily_app_usage_dev_user_day_label"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)

    username: Mapped[str] = mapped_column(String(150), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # The app display name or the website domain — whatever the foreground sample identified.
    label: Mapped[str] = mapped_column(String(260), nullable=False)
    # productive | neutral | unproductive (resolved from the category engine).
    bucket: Mapped[str] = mapped_column(String(20), nullable=False)
    minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
