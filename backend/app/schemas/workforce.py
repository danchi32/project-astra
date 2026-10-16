"""Workforce Insights ("Tracker") — portal read models.

The agent-side ingest model (`ActivityEvent`) lives in schemas/telemetry.py, next to the
rest of the telemetry push it rides in. These are what the portal reads back.
"""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class DailyUserSummaryRead(BaseModel):
    """One (device, Windows account, day) attendance row.

    `device_hostname` is filled by the service for display — the stored row carries only the
    id. The P2/P3 minute fields are null until their collectors ship; the portal shows them
    as "—" rather than 0, because 0 would read as a measured zero.
    """
    model_config = ConfigDict(from_attributes=True)

    device_id: uuid.UUID
    device_hostname: str | None = None
    username: str
    # Null in P1: the Windows account is not yet resolved to a directory user.
    user_id: uuid.UUID | None = None
    day: date

    first_in: datetime | None
    last_out: datetime | None
    worked_minutes: int

    active_minutes: int | None = None
    idle_minutes: int | None = None
    productive_minutes: int | None = None
    neutral_minutes: int | None = None
    unproductive_minutes: int | None = None
    # Minutes flagged as possible mouse-jiggler faking — a review signal, not a verdict.
    suspected_idle_minutes: int | None = None


class WorkSessionRead(BaseModel):
    """One derived work/break span — the raw material behind a day's worked total."""
    model_config = ConfigDict(from_attributes=True)

    device_id: uuid.UUID
    username: str
    day: date
    kind: str
    started_at: datetime
    ended_at: datetime | None


class AppUsageRead(BaseModel):
    """Minutes in one app/website over the requested range, with its productivity bucket."""
    label: str
    bucket: str          # productive | neutral | unproductive
    minutes: int


class UserDetailRead(BaseModel):
    """Everything the per-user drill-down shows: the per-day attendance rows for the range,
    the productivity totals, and the app/website breakdown."""
    username: str
    day_from: date
    day_to: date

    worked_minutes: int
    # Null when no foreground data was collected for this user over the range at all — the
    # UI then shows "—" instead of a measured 0.
    active_minutes: int | None = None
    productive_minutes: int | None = None
    neutral_minutes: int | None = None
    unproductive_minutes: int | None = None
    suspected_idle_minutes: int | None = None

    days: list[DailyUserSummaryRead]
    apps: list[AppUsageRead]
