"""Phase 3 · E3: what the SAVIO browser extension saw on the org's PCs, counts only.

The path is extension → native host → the agent's SYSTEM-owned pipe → this API. The agent
accepts only a fixed schema with no free-text field, and checks it again here: a host name,
the channel, the org's mode and the decision, counts per kind, and flags. The text that was
checked never leaves the PC. `windows_user` is the account Windows named to the agent.

Events about named people are read by admins only, like Workforce Insights.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, GuardEvent
from app.models.base import utcnow
from app.services import guard_approvals, guard_cases
from app.services.browser_policy import FindingKind, entitled, has_control

Reason = Literal["client_request", "approved", "not_real", "own_data", "other"]
RETENTION_DAYS = 180
MAX_BATCH = 500
# Security review M2: a stolen device token must not be able to fill the shared database.
# Events older than this are not taken (an offline laptop's queue is kept two weeks), and one
# PC is taken at most DAILY_CAP events a day; the rest are dropped.
ACCEPT_DAYS = 14
DAILY_CAP = 5000
# DOMAIN\user, as Windows names an account; no characters Windows refuses in either part.
_ACCOUNT = re.compile(r'^(?:[^\\/:*?"<>|]{1,64}\\)?[^\\/\[\]:;|=,+*?<>"]{1,104}$')
_HOST = re.compile(r"^[a-z0-9]([a-z0-9.-]{0,251}[a-z0-9])?$")


class GuardEventIn(BaseModel):
    """The agent's `GuardEvent`, plus when and who. Unknown fields are refused, as on the PC."""
    model_config = ConfigDict(extra="forbid")

    at: datetime
    windows_user: str = Field(min_length=1, max_length=256)
    site: str = Field(max_length=253)
    # "usb": files copied to a USB drive (C3b), recorded by the SAVIO service, not the browser.
    channel: Literal["paste", "drop", "file", "submit", "usb"]
    mode: Literal["log", "warn", "justify", "redact", "approve", "block"]
    action: Literal["allow", "warn", "justify", "redact", "approve", "block"]
    counts: dict[FindingKind, int] = Field(default_factory=dict, max_length=7)
    contact_list: bool = False
    keyword_hits: int = Field(default=0, ge=0, le=200)
    unknown: bool = False
    # D7: the answer to a prompt, and why (a code from a fixed list, never text). "requested"
    # is an approval asked for; "proceeded" after "approve" means an approval was in force.
    outcome: Literal["proceeded", "cancelled", "requested"] | None = None
    reason: Reason | None = None
    # C2: where an uploaded file was downloaded from. A host name only.
    origin: str | None = Field(default=None, max_length=253)

    @model_validator(mode="after")
    def _outcome_fits(self) -> GuardEventIn:
        if self.outcome is None:
            if self.reason is not None:
                raise ValueError("a reason needs an outcome")
            return self
        if self.action == "approve":
            if self.reason is not None:
                raise ValueError("an approval carries no reason")
            return self
        if self.action not in ("warn", "justify") or self.outcome == "requested":
            raise ValueError("only a warn or justify prompt has an outcome")
        needs_reason = self.action == "justify" and self.outcome == "proceeded"
        if needs_reason != (self.reason is not None):
            raise ValueError("a reason is given exactly when going ahead after justify")
        return self

    @field_validator("at")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return v if v.tzinfo else v.replace(tzinfo=UTC)

    @field_validator("site", "origin")
    @classmethod
    def _site(cls, v: str | None) -> str | None:
        if v is not None and not _HOST.match(v):
            raise ValueError("must be a host name")
        return v

    @field_validator("windows_user")
    @classmethod
    def _user(cls, v: str) -> str:
        # Shown to admins: an account name, never a sentence (security review M1).
        if has_control(v) or not _ACCOUNT.match(v):
            raise ValueError("windows_user is not a Windows account name")
        return v

    @field_validator("counts")
    @classmethod
    def _counts(cls, v: dict[str, int]) -> dict[str, int]:
        if any(not 0 <= n <= 1_000_000 for n in v.values()):
            raise ValueError("counts out of range")
        return {k: n for k, n in v.items() if n > 0}


class GuardEventBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: list[GuardEventIn] = Field(max_length=MAX_BATCH)


async def ingest(session: AsyncSession, device: Device, batch: GuardEventBatch) -> int:
    """Store what this device sent; the device comes from its token, never the body. An org
    without AI Guard gets its events dropped (accepted, so the agent stops retrying). Times
    in the future or past the retention window are clock errors and dropped too."""
    if not await entitled(session, device.org_id):
        return 0
    now = utcnow()
    oldest = now - timedelta(days=RETENTION_DAYS)
    accept_from = now - timedelta(days=ACCEPT_DAYS)
    kept = [e for e in batch.events if accept_from <= e.at <= now + timedelta(minutes=5)]
    today = (await session.execute(select(func.count()).select_from(GuardEvent).where(
        GuardEvent.device_id == device.id, GuardEvent.received_at >= now - timedelta(days=1)))).scalar_one()
    kept = kept[:max(0, DAILY_CAP - today)]
    session.add_all(GuardEvent(
        org_id=device.org_id, device_id=device.id, occurred_at=e.at, windows_user=e.windows_user,
        site=e.site, channel=e.channel, mode=e.mode, action=e.action, counts=e.counts,
        contact_list=e.contact_list, keyword_hits=e.keyword_hits, unknown=e.unknown,
        outcome=e.outcome, reason=e.reason, origin=e.origin, received_at=now,
    ) for e in kept)
    # Retention, pruned per device on ingest, as telemetry and workforce samples are.
    await session.execute(delete(GuardEvent).where(GuardEvent.device_id == device.id, GuardEvent.occurred_at < oldest))
    for e in kept:
        if e.action == "approve" and e.outcome == "requested":
            await guard_approvals.request(session, device, e)
    # C1: each person's events join their case, which is scored as a whole.
    await session.flush()
    earliest: dict[str, datetime] = {}
    for e in kept:
        earliest[e.windows_user] = min(e.at, earliest.get(e.windows_user, e.at))
    for user, at in earliest.items():
        await guard_cases.update(session, device.org_id, user, at)
    await session.commit()
    return len(kept)


def _window(org_id, days: int):
    since = utcnow() - timedelta(days=days)
    return GuardEvent.org_id == org_id, GuardEvent.occurred_at >= since


async def summary(session: AsyncSession, org_id, days: int) -> dict:
    where = _window(org_id, days)
    by_action = dict((await session.execute(
        select(GuardEvent.action, func.count()).where(*where).group_by(GuardEvent.action))).all())
    unknown = (await session.execute(select(func.count()).where(*where, GuardEvent.unknown.is_(True)))).scalar_one()
    outcomes = dict((await session.execute(
        select(GuardEvent.outcome, func.count()).where(*where, GuardEvent.outcome.is_not(None))
        .group_by(GuardEvent.outcome))).all())
    reasons = dict((await session.execute(
        select(GuardEvent.reason, func.count()).where(*where, GuardEvent.reason.is_not(None))
        .group_by(GuardEvent.reason).order_by(func.count().desc()))).all())

    sites = (await session.execute(
        select(GuardEvent.site, func.count().label("n"))
        .where(*where).group_by(GuardEvent.site).order_by(func.count().desc(), GuardEvent.site).limit(10))).all()
    people = (await session.execute(
        select(GuardEvent.windows_user, func.count().label("n"))
        .where(*where).group_by(GuardEvent.windows_user).order_by(func.count().desc(), GuardEvent.windows_user).limit(10))).all()

    # ponytail: kinds are summed in Python over the window's count maps (a JSON column, and
    # SQLite in tests). Fine for an SMB's months of events; upgrade path is a per-kind column
    # or a daily roll-up table when an org outgrows it.
    kinds: Counter[str] = Counter()
    contact_lists = keyword_events = 0
    for counts, contact, keywords in (await session.execute(
            select(GuardEvent.counts, GuardEvent.contact_list, GuardEvent.keyword_hits).where(*where))).all():
        kinds.update({k: 1 for k, n in (counts or {}).items() if n > 0})   # events, not items
        contact_lists += contact
        keyword_events += keywords > 0

    return {
        "days": days,
        "total": sum(by_action.values()),
        "allowed": by_action.get("allow", 0),
        "warned": by_action.get("warn", 0),
        "justified": by_action.get("justify", 0),
        "redacted": by_action.get("redact", 0),
        "blocked": by_action.get("block", 0),
        "unknown": unknown,
        "went_ahead": outcomes.get("proceeded", 0),
        "stopped": outcomes.get("cancelled", 0),
        "reasons": reasons,
        "kinds": dict(kinds.most_common()),
        "contact_lists": contact_lists,
        "keyword_events": keyword_events,
        "top_sites": [{"site": s, "events": n} for s, n in sites],
        "top_people": [{"windows_user": u, "events": n} for u, n in people],
    }


async def recent(session: AsyncSession, org_id, days: int, limit: int, offset: int) -> list[tuple[GuardEvent, str]]:
    return list((await session.execute(
        select(GuardEvent, Device.hostname)
        .join(Device, Device.id == GuardEvent.device_id)
        .where(*_window(org_id, days))
        .order_by(GuardEvent.occurred_at.desc(), GuardEvent.id)
        .limit(limit).offset(offset)
    )).all())
