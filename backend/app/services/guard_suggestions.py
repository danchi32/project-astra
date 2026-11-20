"""Phase 3 · D5 slice 2: policy suggestions from what AI Guard has seen.

Each suggestion is a fixed rule in this file, computed from the org's own evidence (the file
map from D5, the extension's events from E3) and its current policy. Each one says why, in
numbers, and carries the exact change it would make. Nothing is applied until an admin
presses Apply, which goes through the same audited policy update as the Browser policy page.
An admin can dismiss a suggestion for good. A suggestion whose condition no longer holds
(already applied, or the evidence went away) simply stops appearing.
"""
from __future__ import annotations

import hashlib
import re
from datetime import timedelta

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DailyAppUsage, GuardEvent, GuardSuggestionDismissal, Organization, User
from app.models.base import utcnow
from app.services import browser_policy, guard_discovery, guard_sites
from app.services.audit import AuditService
from app.services.browser_policy import BrowserPolicyBody
from app.services.entitlements import WORKFORCE_INSIGHTS, features_for

WINDOW = timedelta(days=14)
AI_SITES = list(browser_policy.SITE_CATEGORIES["ai_chat"][1])
FOUND_KINDS = ("file_sharing", "personal_email", "paste_sites")
# S3: an unproductive site worth blocking takes at least this many minutes a day across the
# org, used by at least this many people; a neutral one is worth a second look at an hour.
SINK_MINUTES, NEUTRAL_MINUTES, SINK_PEOPLE = 30, 60, 3
# Not a browser-policy field: applying it adds Tracker overrides (domain → unproductive).
TRACKER_UNPRODUCTIVE = "tracker_unproductive"
_SITE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")


class SuggestionNotFound(LookupError):
    pass


class SuggestionChanged(ValueError):
    """What the suggestion would do now differs from what the admin saw, or no longer fits."""


def _is_ai(site: str) -> bool:
    return any(site == s or site.endswith("." + s) for s in AI_SITES)


def _plural(n: int, word: str) -> str:
    if word == "person":
        return f"{n:,} {'person' if n == 1 else 'people'}"
    return f"{n:,} {word}{'' if n == 1 else 's'}"


def _hours(minutes: int) -> str:
    return f"{minutes} minutes" if minutes < 90 else f"{minutes / 60:.1f} hours".replace(".0 ", " ")


def _digest(items: list[str]) -> str:
    """A suggestion keyed by its exact set, so a new set brings a new card after a dismissal."""
    return hashlib.sha256(",".join(items).encode()).hexdigest()[:12]


async def _evidence(session: AsyncSession, org_id) -> dict:
    since = utcnow() - WINDOW
    rows = (await session.execute(
        select(GuardEvent.site, GuardEvent.contact_list, func.count())
        .where(GuardEvent.org_id == org_id, GuardEvent.occurred_at >= since)
        .group_by(GuardEvent.site, GuardEvent.contact_list)
    )).all()
    events = sum(n for _, _, n in rows)
    ai = sum(n for site, _, n in rows if _is_ai(site))
    event_lists = sum(n for _, contact, n in rows if contact)
    disc = await guard_discovery.for_org(session, org_id)
    # S1: risky sites SAVIO's AI recognised (the fixed list does not know them), by registrable
    # domain, with how many times data went there.
    known = await guard_sites.learned(session)
    found: dict[str, list] = {}
    for site, _, n in rows:
        kind, source = guard_sites.kind_of(site, known)
        if source == "ai" and kind in FOUND_KINDS:
            entry = found.setdefault(guard_sites.registrable(site), [kind, 0])
            entry[1] += n
    return {"events": events, "ai_events": ai, "event_contact_lists": event_lists,
            "file_contact_lists": disc["contact_lists"], "files": disc["files_with_findings"], "pcs": disc["pcs"],
            "found": found, "time": await _time_sinks(session, org_id)}


async def _time_sinks(session: AsyncSession, org_id) -> dict[str, dict]:
    """S3: where the org's time goes on the web, from Tracker, only where the org also has Tracker.
    Org totals per website over the window: minutes a day and how many people, by Tracker's
    bucket. Never who."""
    org = await session.get(Organization, org_id)
    if org is None or WORKFORCE_INSIGHTS not in features_for(org.plan, org.entitlement_overrides):
        return {}
    since = (utcnow() - WINDOW).date()
    rows = (await session.execute(
        select(DailyAppUsage.label, DailyAppUsage.bucket, func.sum(DailyAppUsage.minutes),
               func.count(func.distinct(DailyAppUsage.username)))
        .where(DailyAppUsage.org_id == org_id, DailyAppUsage.day >= since)
        .group_by(DailyAppUsage.label, DailyAppUsage.bucket))).all()
    overridden = set(((org.workforce_categories or {}).get("domain") or {}).keys())
    out: dict[str, dict] = {}
    for label, bucket, minutes, people in rows:
        site = (label or "").lower()
        if not _SITE.match(site) or site.endswith(".exe"):
            continue   # an app, not a website
        # A site the admin already classed is theirs to decide; its stored days may lag behind.
        e = out.setdefault(site, {"bucket": "overridden" if site in overridden else bucket, "per_day": 0, "people": 0})
        e["per_day"] += round((minutes or 0) / WINDOW.days)
        e["people"] = max(e["people"], people)
    return out


def _rules(p: BrowserPolicyBody, ev: dict, pilot: bool = False) -> list[dict]:
    """Every rule whose condition holds now. `patch` is the change; `changes` says it in words."""
    out: list[dict] = []
    extension = (p.chrome_extension_id or p.edge_extension_id or p.firefox_extension_id) is not None

    # E8: during the pilot recording is the point; this is the card that greets its end.
    if p.guard_mode == "log" and ev["events"] > 0 and not pilot:
        mostly_ai = ev["ai_events"] * 2 >= ev["events"]
        out.append({
            "key": "leave_record_only",
            "title": "Hide sensitive numbers when people paste into AI chats" if mostly_ai
                     else "Ask people before sensitive data leaves the browser",
            "why": f"In the last 14 days the extension saw sensitive data pasted or uploaded {_plural(ev['events'], 'time')}"
                   + (f", {ev['ai_events']:,} of them on AI chat sites" if ev["ai_events"] else "")
                   + ". It is only recording so far.",
            "patch": {"guard_mode": "redact" if mostly_ai else "warn"},
            "changes": ["Mode: Hide the sensitive parts" if mostly_ai else "Mode: Warn"],
        })

    contact_lists = ev["file_contact_lists"] + ev["event_contact_lists"]
    if contact_lists > 0 and "file_sharing" not in p.blocked_categories:
        out.append({
            "key": "block_file_sharing",
            "title": "Block personal file-sharing sites",
            "why": f"{_plural(contact_lists, 'contact list')} found"
                   + (f" in files on {_plural(ev['pcs'], 'PC')}" if ev["file_contact_lists"] else "")
                   + (" and in what people pasted or uploaded" if ev["event_contact_lists"] else "")
                   + ". Sites like these are the usual way a list leaves the company.",
            "patch": {"blocked_categories": ["file_sharing"]},
            "changes": ["Block the category: Personal file-sharing (WeTransfer, Mega and "
                        + f"{len(browser_policy.SITE_CATEGORIES['file_sharing'][1]) - 2} more)"],
        })

    # S1: sites the fixed list does not know, that SAVIO's AI recognised as personal file sharing,
    # personal e-mail or paste sites, which people sent sensitive data to and which are not blocked.
    blocked = set(p.blocked_sites) | set(browser_policy.category_hosts(p.blocked_categories))
    fresh = sorted(h for h in ev.get("found", {})
                   if not any(h == b or h.endswith("." + b) for b in blocked))
    if fresh:
        names ={"file_sharing": "file sharing", "personal_email": "personal e-mail", "paste_sites": "paste site"}
        times = sum(ev["found"][h][1] for h in fresh)
        out.append({
            # Keyed by the set, so a site found later brings a new card even after a dismissal.
            "key": "block_found:" + _digest(fresh),
            "title": f"Block {_plural(len(fresh), 'risky site')} SAVIO found",
            "why": f"Not on any list, but SAVIO recognised {', '.join(fresh[:5])}{' and more' if len(fresh) > 5 else ''} "
                   f"as personal sites ({', '.join(sorted({names[ev['found'][h][0]] for h in fresh}))}), and sensitive "
                   f"data went to them {_plural(times, 'time')} in the last 14 days.",
            "patch": {"blocked_sites": fresh},
            "changes": [f"Block {h} ({names[ev['found'][h][0]]})" for h in fresh],
        })

    # S3 (with Tracker): websites that take a lot of the org's time. Org totals only.
    time = ev.get("time", {})
    sinks = sorted((s for s, t in time.items() if t["bucket"] == "unproductive" and t["per_day"] >= SINK_MINUTES
                    and t["people"] >= SINK_PEOPLE and not any(s == b or s.endswith("." + b) for b in blocked)),
                   key=lambda s: -time[s]["per_day"])[:10]
    if sinks:
        out.append({
            "key": "block_time:" + _digest(sinks),
            "title": f"Block {_plural(len(sinks), 'time-wasting site')}",
            "why": "From Tracker, the last 14 days: " + "; ".join(
                f"{s} takes {_hours(time[s]['per_day'])} a day across {_plural(time[s]['people'], 'person')}"
                for s in sinks[:3]) + (" and more" if len(sinks) > 3 else "") + ".",
            "patch": {"blocked_sites": sinks},
            "changes": [f"Block {s}" for s in sinks],
        })
    neutral = sorted((s for s, t in time.items() if t["bucket"] == "neutral" and t["per_day"] >= NEUTRAL_MINUTES
                      and t["people"] >= SINK_PEOPLE), key=lambda s: -time[s]["per_day"])[:10]
    if neutral:
        out.append({
            "key": "unproductive:" + _digest(neutral),
            "title": f"Count {_plural(len(neutral), 'site')} as unproductive?",
            "why": "Tracker counts these as neutral, but they take a lot of time: " + "; ".join(
                f"{s}, {_hours(time[s]['per_day'])} a day across {_plural(time[s]['people'], 'person')}"
                for s in neutral[:3]) + (" and more" if len(neutral) > 3 else "") + ". Your call: they may be work.",
            "patch": {TRACKER_UNPRODUCTIVE: neutral},
            "changes": [f"Tracker: count {s} as unproductive" for s in neutral],
        })

    if extension and not p.incognito_off:
        out.append({
            "key": "no_private_windows",
            "title": "Turn off private windows",
            "why": "The SAVIO extension does not run in incognito / InPrivate windows, so anything pasted there is not checked.",
            "patch": {"incognito_off": True},
            "changes": ["No incognito / InPrivate / private windows"],
        })

    if extension and p.extension_install == "store" and not p.extension_developer_mode_off:
        out.append({
            "key": "no_unpacked_extensions",
            "title": "Turn off extension developer mode",
            "why": "With developer mode on, anyone can load an unpacked extension next to SAVIO's, including one that "
                   "reads what is typed.",
            "patch": {"extension_developer_mode_off": True},
            "changes": ["No extension developer mode"],
        })

    missing_ai = [s for s in AI_SITES if s not in p.guard_watched_sites]
    if p.guard_watched_sites and missing_ai and (ev["files"] > 0 or ev["events"] > 0):
        out.append({
            "key": "watch_ai_sites",
            "title": "Check AI chat sites too",
            "why": f"Only the sites you listed are checked, and {_plural(len(missing_ai), 'AI chat site')} "
                   f"{'is' if len(missing_ai) == 1 else 'are'} not among them, while sensitive data is on your PCs"
                   f" ({_plural(ev['files'], 'file')} found).",
            "patch": {"guard_watched_sites": missing_ai},
            "changes": [f"Also check {', '.join(missing_ai)}"],
        })

    if not p.discovery_enabled and ev["events"] > 0:
        out.append({
            "key": "find_files",
            "title": "Find where sensitive files are kept",
            "why": f"People handled sensitive data {_plural(ev['events'], 'time')} in the browser in the last 14 days. "
                   "A weekly check shows which folders it comes from (counts only).",
            "patch": {"discovery_enabled": True},
            "changes": ["Find where sensitive files are kept: on"],
        })
    return out


async def _current(session: AsyncSession, org_id) -> BrowserPolicyBody:
    row = await browser_policy.get(session, org_id)
    return BrowserPolicyBody(**row.policy) if row else BrowserPolicyBody()


async def suggestions(session: AsyncSession, org_id) -> list[dict]:
    dismissed = set((await session.execute(
        select(GuardSuggestionDismissal.key).where(GuardSuggestionDismissal.org_id == org_id))).scalars())
    pilot = browser_policy.pilot_until(await browser_policy.get(session, org_id)) is not None
    rules = _rules(await _current(session, org_id), await _evidence(session, org_id), pilot)
    return [s for s in rules if s["key"] not in dismissed]


async def _find(session: AsyncSession, org_id, key: str) -> dict:
    for s in await suggestions(session, org_id):
        if s["key"] == key:
            return s
    raise SuggestionNotFound()


async def apply(session: AsyncSession, *, actor: User, key: str, seen_changes: list[str]):
    """Apply one suggestion through the same audited update as the Browser policy page. Lists
    are added to, never replaced. Refused if it no longer applies, if it would now change
    something other than what the admin saw, or if the result would not be a valid policy."""
    s = await _find(session, actor.org_id, key)
    if s["changes"] != seen_changes:
        raise SuggestionChanged("This suggestion changed since you looked at it. Review it again.")
    if TRACKER_UNPRODUCTIVE in s["patch"]:
        # S3: a Tracker override, not a browser setting. Added to the org's rules, audited the way
        # Tracker's own settings page audits them; the browser policy is untouched.
        org = await session.get(Organization, actor.org_id)
        rules = dict(org.workforce_categories or {})
        added = {d: "unproductive" for d in s["patch"][TRACKER_UNPRODUCTIVE]}
        org.workforce_categories = {"domain": {**rules.get("domain", {}), **added}, "app": rules.get("app", {})}
        audit = AuditService(session)
        await audit.record(org_id=actor.org_id, actor_id=actor.id, action="workforce.categories.update",
                           target_type="organization", target_id=str(actor.org_id),
                           detail={"domain": added, "via": "AI Guard suggestion"})
        await audit.record(org_id=actor.org_id, actor_id=actor.id, action="guard.suggestion_apply",
                           target_type="organization", target_id=str(actor.org_id),
                           detail={"suggestion": key, "changes": s["changes"]})
        await session.commit()
        return await browser_policy.get(session, actor.org_id)
    current = (await _current(session, actor.org_id)).model_dump()
    for field, value in s["patch"].items():
        current[field] = current[field] + [v for v in value if v not in current[field]] if isinstance(value, list) else value
    try:
        body = BrowserPolicyBody(**current)
    except ValidationError as e:
        raise SuggestionChanged(f"Applying this would make the policy invalid: {e.errors()[0]['msg']}") from None
    await AuditService(session).record(
        org_id=actor.org_id, actor_id=actor.id, action="guard.suggestion_apply",
        target_type="organization", target_id=str(actor.org_id), detail={"suggestion": key, "changes": s["changes"]},
    )
    return await browser_policy.put(session, actor=actor, body=body)


async def dismiss(session: AsyncSession, *, actor: User, key: str) -> None:
    await _find(session, actor.org_id, key)   # also refuses one already dismissed
    if await session.get(GuardSuggestionDismissal, (actor.org_id, key)) is not None:
        return                                  # two admins at once: the first one counts
    session.add(GuardSuggestionDismissal(org_id=actor.org_id, key=key, dismissed_by_user_id=actor.id,
                                         dismissed_at=utcnow()))
    await AuditService(session).record(
        org_id=actor.org_id, actor_id=actor.id, action="guard.suggestion_dismiss",
        target_type="organization", target_id=str(actor.org_id), detail={"suggestion": key},
    )
    await session.commit()
