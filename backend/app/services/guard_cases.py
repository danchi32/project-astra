"""Phase 3c · C1: cases, not alerts.

A DLP that raises one alert per event buries IT: in the Cloud Security Alliance's 2026 survey,
over half of teams said most of their DLP alerts were false positives. SAVIO joins one person's
events into one case while they keep coming, scores the whole story, says why in plain words,
and notifies only when a case is high: once per case, never per event.

The score is fixed code, not a model: every point can be explained, and nothing an attacker
types can change it. It reads only what the events hold (host names, channels, decisions and
counts), never content.

- Per event with something sensitive in it:
    how it ended × where it went × (1 + items/50 + 5 for a contact list + 2 for a keyword)
  how it ended: went ahead after a warning 3, nothing stopped it (record-only) 2, asked IT or
  stopped by SAVIO 1, hidden or stopped by the person 0.5. Where: personal file sharing, personal
  e-mail and paste sites 3; AI chat, messaging and social media 2; a site new to the org this
  week 2; anything else 1. Items are capped at 500 an event. ×1.5 when the file was downloaded
  from another site (C2): data moving from one system to another.
- Plus 5 for every extra site in the same case.
- High from 40, medium from 10.

ponytail: site risk comes from the fixed categories in `browser_policy.SITE_CATEGORIES`. The
upgrade path is S1, the AI's own site categories, plugged in at `site_kind`.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Device,
    GuardCase,
    GuardEvent,
    GuardQuietSite,
    NotificationCategory,
    NotificationSeverity,
    OrgBrowserPolicy,
    User,
)
from app.models.base import as_utc, utcnow
from app.services.audit import AuditService
from app.services.browser_policy import SITE_CATEGORIES
from app.services.notifications import NotificationService

CASE_GAP = timedelta(hours=48)       # quiet this long and the next event starts a new case
NEW_SITE = timedelta(days=7)         # a site first seen in the org this recently is "new"
HIGH, MEDIUM = 40, 10
RISKY = {"file_sharing": 3, "personal_email": 3, "paste_sites": 3, "ai_chat": 2, "messaging": 2, "social_media": 2}
LABELS = {
    "Aadhaar": "Aadhaar number", "Pan": "PAN", "Gstin": "GSTIN", "PaymentCard": "card number",
    "IndianMobile": "mobile number", "Email": "e-mail address", "BankAccount": "bank account number",
}
# As they read inside a sentence ("to wetransfer.com (personal file sharing)").
KIND_NAMES = {"file_sharing": "personal file sharing", "personal_email": "personal e-mail", "ai_chat": "AI chat",
              "messaging": "messaging on the web", "social_media": "social media", "paste_sites": "a paste site"}


def site_kind(host: str) -> str | None:
    """The category a host (or its parent) is listed under, if any."""
    for key, (_, hosts) in SITE_CATEGORIES.items():
        if any(host == h or host.endswith("." + h) for h in hosts):
            return key
    return None


def _same_place(a: str, b: str) -> bool:
    """A download and an upload on the same site (or one inside the other) is not data moving."""
    return a == b or a.endswith("." + b) or b.endswith("." + a)


def _how(e) -> float:
    if e.outcome == "proceeded" and e.action in ("warn", "justify"):
        return 3
    if e.action == "allow":
        return 2
    if e.action == "redact" or e.outcome == "cancelled" or (e.action == "approve" and e.outcome == "proceeded"):
        return 0.5
    return 1   # blocked, asked IT, or a prompt not answered yet


def _items(e, ignore: set[str]) -> int:
    return sum(n for k, n in (e.counts or {}).items() if k not in ignore)


def score(events, ignore: set[str], new_sites: set[str]) -> tuple[int, str, dict]:
    """The case's score, level and summary from its events. Pure, so it is tested directly."""
    total = 0.0
    kinds: dict[str, int] = defaultdict(int)
    sites: dict[str, dict] = {}
    went_ahead = blocked = contact_lists = keyword_events = 0
    origins: dict[str, int] = {}
    for e in events:
        items = _items(e, ignore)
        if not (items or e.contact_list or e.keyword_hits):
            continue   # e-mail addresses only, or could not be checked: not part of a story
        kind = site_kind(e.site)
        where = RISKY.get(kind, 2 if e.site in new_sites else 1)
        origin = getattr(e, "origin", None)
        moved = origin is not None and not _same_place(origin, e.site)
        total += (_how(e) * where * (1.5 if moved else 1)
                  * (1 + min(items, 500) / 50 + 5 * e.contact_list + 2 * (e.keyword_hits > 0)))
        for k, n in (e.counts or {}).items():
            if k not in ignore:
                kinds[k] += n
        s = sites.setdefault(e.site, {"site": e.site, "kind": kind, "new": e.site in new_sites, "events": 0,
                                      "items": 0, "contact_lists": 0, "went_ahead": 0, "blocked": 0,
                                      "channels": [], "origins": []})
        s["events"] += 1
        if moved and origin not in s["origins"]:
            s["origins"].append(origin)
            origins[origin] = origins.get(origin, 0) + 1
        s["items"] += items
        s["contact_lists"] += e.contact_list
        if e.channel not in s["channels"]:
            s["channels"].append(e.channel)
        if e.outcome == "proceeded" and e.action in ("warn", "justify"):
            s["went_ahead"] += 1
            went_ahead += 1
        if e.action == "block":
            s["blocked"] += 1
            blocked += 1
        contact_lists += e.contact_list
        keyword_events += e.keyword_hits > 0
    total += 5 * max(0, len(sites) - 1)
    points = round(total)
    level = "high" if points >= HIGH else "medium" if points >= MEDIUM else "low"

    ranked = sorted(sites.values(), key=lambda s: (-(RISKY.get(s["kind"], 1) * (s["items"] + 50 * s["contact_lists"])),
                                                   s["site"]))
    reasons = []
    if kinds:
        top = sorted(kinds.items(), key=lambda kv: -kv[1])[:3]
        reasons.append(", ".join(f"{n} {LABELS.get(k, k)}{'s' if n > 1 else ''}" for k, n in top))
    if contact_lists:
        reasons.append("a contact list" if contact_lists == 1 else f"{contact_lists} contact lists")
    if keyword_events:
        reasons.append("a restricted keyword" if keyword_events == 1 else f"restricted keywords {keyword_events} times")
    for s in ranked[:3]:
        what = KIND_NAMES.get(s["kind"]) or ("a site new to your organization" if s["new"] else None)
        reasons.append(f"to {s['site']}" + (f" ({what})" if what else ""))
    if origins:
        top = sorted(origins, key=lambda o: (-origins[o], o))[:2]
        reasons.append("files downloaded from " + " and ".join(top))
    if went_ahead:
        reasons.append("went ahead after a warning" + (f" {went_ahead} times" if went_ahead > 1 else ""))
    if blocked:
        reasons.append(f"SAVIO blocked {blocked} attempt{'s' if blocked > 1 else ''}")
    if len(sites) > 1:
        reasons.append(f"across {len(sites)} sites")
    return points, level, {"reasons": reasons, "sites": ranked, "kinds": dict(kinds),
                           "events": sum(s["events"] for s in sites.values())}


async def _ignore(session: AsyncSession, org_id) -> set[str]:
    row = await session.get(OrgBrowserPolicy, org_id)
    return set((row.policy or {}).get("guard_ignore_kinds", ["Email"]) if row else ["Email"])


async def _quiet(session: AsyncSession, org_id) -> set[str]:
    return set((await session.execute(select(GuardQuietSite.site).where(GuardQuietSite.org_id == org_id))).scalars())


async def update(session: AsyncSession, org_id, windows_user: str, earliest_new) -> GuardCase | None:
    """Bring this person's case up to date after new events, the earliest of which happened at
    `earliest_new` (called from ingest, which commits). A case opens with the first event that
    matters and stays open while events keep coming; after CASE_GAP of quiet the next one starts
    a new case. A case IT closed is never reopened: what comes after it is a new case.
    ponytail: an event older than its open case's start (a laptop that was offline for days) is
    left out of it; it is still under "What was found"."""
    quiet = await _quiet(session, org_id)
    case = (await session.execute(
        select(GuardCase).where(GuardCase.org_id == org_id, GuardCase.windows_user == windows_user,
                                GuardCase.status == "open")
        .order_by(GuardCase.last_event_at.desc()).limit(1))).scalars().first()
    last_closed = (await session.execute(select(func.max(GuardCase.last_event_at)).where(
        GuardCase.org_id == org_id, GuardCase.windows_user == windows_user, GuardCase.status == "closed"))).scalar()
    since = as_utc(case.opened_at) if case else as_utc(earliest_new)
    if last_closed is not None:
        since = max(since, as_utc(last_closed) + timedelta(microseconds=1))
    events = [e for e in (await session.execute(
        select(GuardEvent).where(GuardEvent.org_id == org_id, GuardEvent.windows_user == windows_user,
                                 GuardEvent.occurred_at >= since)
        .order_by(GuardEvent.occurred_at))).scalars() if e.site not in quiet]
    if case is not None:
        newer = [e for e in events if as_utc(e.occurred_at) > as_utc(case.last_event_at)]
        if newer and as_utc(newer[0].occurred_at) - as_utc(case.last_event_at) > CASE_GAP:
            # Quiet for longer than the gap: that case stays as it was, and these start another.
            case, events = None, newer
    if not events:
        return case
    ignore = await _ignore(session, org_id)
    first_seen = dict((await session.execute(
        select(GuardEvent.site, func.min(GuardEvent.occurred_at)).where(
            GuardEvent.org_id == org_id, GuardEvent.site.in_({e.site for e in events}))
        .group_by(GuardEvent.site))).all())
    new_sites = {s for s, t in first_seen.items() if as_utc(t) >= utcnow() - NEW_SITE}
    points, level, summary = score(events, ignore, new_sites)
    if not summary["events"]:
        return case
    devices = (await session.execute(select(Device.hostname).where(
        Device.id.in_({e.device_id for e in events})).order_by(Device.hostname))).scalars().all()
    if case is None:
        case = GuardCase(org_id=org_id, windows_user=windows_user, status="open",
                         opened_at=min(e.occurred_at for e in events))
        session.add(case)
    case.last_event_at = max(e.occurred_at for e in events)
    case.score, case.level, case.summary = points, level, {**summary, "devices": list(devices)}
    if level == "high" and case.notified_at is None:
        # Once per case. Notifications are seen by everyone in the org, so no name in it: the
        # person is on the Cases page, which only admins can open.
        case.notified_at = utcnow()
        await session.flush()
        await NotificationService(session).notify(
            org_id=org_id, category=NotificationCategory.SYSTEM, severity=NotificationSeverity.CRITICAL,
            title="AI Guard: a high-risk case",
            message="Sensitive data is leaving in a way that needs a look: " + "; ".join(summary["reasons"][:2]),
            link="/guard/cases",
        )
    return case


async def cases(session: AsyncSession, org_id, status: str, limit: int = 100) -> list[GuardCase]:
    order = (GuardCase.score.desc(), GuardCase.last_event_at.desc()) if status == "open" \
        else (GuardCase.closed_at.desc(),)
    return list((await session.execute(
        select(GuardCase).where(GuardCase.org_id == org_id, GuardCase.status == status)
        .order_by(*order).limit(limit))).scalars())


async def overview(session: AsyncSession, org_id) -> dict:
    """Open cases by level, the quiet sites, and how many events those sites had in 30 days."""
    by_level = dict((await session.execute(select(GuardCase.level, func.count()).where(
        GuardCase.org_id == org_id, GuardCase.status == "open").group_by(GuardCase.level))).all())
    quiet = sorted(await _quiet(session, org_id))
    quiet_events = (await session.execute(select(func.count()).select_from(GuardEvent).where(
        GuardEvent.org_id == org_id, GuardEvent.site.in_(quiet),
        GuardEvent.occurred_at >= utcnow() - timedelta(days=30)))).scalar_one() if quiet else 0
    return {"open": {k: by_level.get(k, 0) for k in ("high", "medium", "low")},
            "quiet_sites": quiet, "quiet_events_30d": quiet_events}


async def close(session: AsyncSession, *, actor: User, case_id, resolution: str, quiet_site: str | None) -> GuardCase:
    case = await session.get(GuardCase, case_id)
    if case is None or case.org_id != actor.org_id:
        raise LookupError("No such case.")
    if case.status != "open":
        raise ValueError("This case is already closed.")
    if quiet_site is not None:
        if resolution != "expected" or quiet_site not in {s["site"] for s in case.summary.get("sites", [])}:
            raise ValueError("Only a site in this case, closed as expected, can be made quiet.")
        if await session.get(GuardQuietSite, (actor.org_id, quiet_site)) is None:
            session.add(GuardQuietSite(org_id=actor.org_id, site=quiet_site, created_by_user_id=actor.id))
    case.status, case.resolution, case.closed_by_user_id, case.closed_at = "closed", resolution, actor.id, utcnow()
    await AuditService(session).record(
        org_id=actor.org_id, actor_id=actor.id, action="guard.case_close", target_type="guard_case",
        target_id=str(case.id), detail={"resolution": resolution, "level": case.level, "quiet_site": quiet_site},
    )
    await session.commit()
    return case


async def unquiet(session: AsyncSession, *, actor: User, site: str) -> None:
    row = await session.get(GuardQuietSite, (actor.org_id, site))
    if row is None:
        raise LookupError("That site is not quiet.")
    await session.delete(row)
    await AuditService(session).record(
        org_id=actor.org_id, actor_id=actor.id, action="guard.quiet_site_remove", target_type="organization",
        target_id=str(actor.org_id), detail={"site": site},
    )
    await session.commit()
