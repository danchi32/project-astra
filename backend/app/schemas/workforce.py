"""Workforce Insights ("Tracker") — portal read models.

The agent-side ingest model (`ActivityEvent`) lives in schemas/telemetry.py, next to the
rest of the telemetry push it rides in. These are what the portal reads back.
"""
import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.grouping import COLOUR_PATTERN
from app.services.workforce_categories import BUCKETS

# A customer's override map is small by design — it reclassifies the handful of apps/sites that
# matter to them, not a directory. Cap it so a stored config stays bounded and cheap to apply.
_MAX_RULES = 300


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


class CategoryOverrides(BaseModel):
    """Per-org productivity reclassification: which apps/domains this customer counts as
    productive / neutral / unproductive, overriding the built-in taxonomy. Keys are normalised
    (lower-cased, trimmed; a leading ``www.`` is dropped from a domain) and values must be one
    of the three buckets — anything else is rejected at the edge rather than stored and ignored."""

    # host -> bucket, e.g. {"youtube.com": "productive"}
    domain: dict[str, str] = Field(default_factory=dict)
    # process/app keyword (substring, lower-cased) -> bucket, e.g. {"myinternaltool": "productive"}
    app: dict[str, str] = Field(default_factory=dict)

    @field_validator("domain", "app")
    @classmethod
    def _normalise(cls, raw: dict[str, str], info) -> dict[str, str]:
        out: dict[str, str] = {}
        for key, bucket in raw.items():
            k = str(key).strip().lower()
            if info.field_name == "domain" and k.startswith("www."):
                k = k[4:]
            if not k:
                continue  # an empty key is a no-op rule, not an error
            if bucket not in BUCKETS:
                raise ValueError(
                    f"{info.field_name} rule '{k}' has invalid bucket '{bucket}'; "
                    f"expected one of {', '.join(BUCKETS)}"
                )
            out[k] = bucket
        if len(out) > _MAX_RULES:
            raise ValueError(f"too many {info.field_name} rules (max {_MAX_RULES})")
        return out


class CategoryConfigRead(BaseModel):
    """What the category-config screen needs: the three buckets, the built-in defaults (shown so
    an admin can see what a rule would change), and the org's own overrides."""

    buckets: list[str]
    builtin: CategoryOverrides
    overrides: CategoryOverrides


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
    idle_minutes: int | None = None
    productive_minutes: int | None = None
    neutral_minutes: int | None = None
    unproductive_minutes: int | None = None
    suspected_idle_minutes: int | None = None

    days: list[DailyUserSummaryRead]
    apps: list[AppUsageRead]


# ── Department shifts ─────────────────────────────────────────────────────────

_DEFAULT_WORKING_DAYS = [0, 1, 2, 3, 4]  # Mon–Fri


class WorkShiftWrite(BaseModel):
    """Create/update body for a department shift. Times are minutes from LOCAL midnight in
    `timezone`; end <= start means the shift runs past midnight (a night shift)."""

    name: str = Field(min_length=1, max_length=120)
    timezone: str = Field(min_length=1, max_length=64)
    start_minute: int = Field(ge=0, le=1439)
    end_minute: int = Field(ge=0, le=1439)
    working_days: list[int] = Field(default_factory=lambda: list(_DEFAULT_WORKING_DAYS))
    colour: str | None = Field(default=None, pattern=COLOUR_PATTERN)

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, v: str) -> str:
        tz = v.strip()
        try:
            ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Unknown timezone '{v}'") from exc
        return tz

    @field_validator("working_days")
    @classmethod
    def _valid_days(cls, v: list[int]) -> list[int]:
        days = sorted(set(v))
        if not days:
            raise ValueError("A shift needs at least one working day.")
        if any(d < 0 or d > 6 for d in days):
            raise ValueError("working_days are 0 (Monday) … 6 (Sunday).")
        return days

    @model_validator(mode="after")
    def _start_differs_from_end(self) -> "WorkShiftWrite":
        if self.start_minute == self.end_minute:
            raise ValueError("A shift's start and end time cannot be identical.")
        return self


class WorkShiftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    timezone: str
    start_minute: int
    end_minute: int
    working_days: list[int]
    colour: str | None = None
    # How many teams are assigned this shift — filled by the service, shown so an admin sees a
    # shift is in use before deleting it.
    team_count: int = 0


class TeamShiftRead(BaseModel):
    """One team with its current shift assignment — the Configuration > Shifts assignment list."""

    team_id: uuid.UUID
    team_name: str
    member_count: int
    shift_id: uuid.UUID | None = None
    shift_name: str | None = None


class ShiftAssignmentWrite(BaseModel):
    """Assign (or, with null, clear) the shift a team works."""

    shift_id: uuid.UUID | None = None


# ── Account → directory-user mapping ──────────────────────────────────────────


class TrackedAccountRead(BaseModel):
    """One tracked Windows account with its mapping and some context, for the identity screen."""

    username: str
    user_id: uuid.UUID | None = None
    # Filled when the account is mapped to a directory user.
    user_name: str | None = None
    user_email: str | None = None
    # Null only for an account mapped before any attendance exists for it (unusual — the screen
    # lists accounts seen in attendance). The portal shows "—" for a null.
    last_seen: date | None = None
    device_count: int


class AccountAssignWrite(BaseModel):
    """Map a tracked account to a directory user, or clear it with a null user_id."""

    username: str = Field(min_length=1, max_length=150)
    user_id: uuid.UUID | None = None


# ── Team rollups ──────────────────────────────────────────────────────────────


class TeamRollupRead(BaseModel):
    """One team's attendance + productivity over a range, summed across its members' accounts.

    `member_count` is everyone on the team; `tracked_members` is how many of them actually have
    tracked activity in the range. The productivity fields are null when no member had a measured
    value (shown as "—"), never a misleading 0."""

    team_id: uuid.UUID
    team_name: str
    colour: str | None = None
    shift_name: str | None = None
    member_count: int
    tracked_members: int
    worked_minutes: int
    active_minutes: int | None = None
    idle_minutes: int | None = None
    productive_minutes: int | None = None
    neutral_minutes: int | None = None
    unproductive_minutes: int | None = None
