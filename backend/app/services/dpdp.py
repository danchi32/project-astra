"""Phase 3b · I1: DPDP readiness, from what SAVIO already knows.

A score and a task list: each item is something an organisation is commonly expected to have in
place for personal data, checked against SAVIO's own records (the file map, the security checks,
AI Guard's settings, cases), with the evidence in numbers and a link to where it is fixed. Plus a
map of where personal data is kept and where it goes, in counts.

It says what SAVIO saw, never what the law requires: the Act's and Rules' obligations and
timelines are for the organisation's counsel to confirm, and every page and answer says so.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GuardCase, GuardDiscovery, GuardEvent, User
from app.models.base import as_utc, utcnow
from app.services import browser_policy, guard_discovery, guard_events, guard_sites
from app.services.audit import AuditService
from app.services.browser_policy import BrowserPolicyBody
from app.services.compliance import ComplianceService
from app.services.settings import SettingsService

DISCLAIMER = ("This shows what SAVIO's own records say about your safeguards. It is not legal advice: confirm "
              "what the DPDP Act and Rules require of your organisation with your counsel.")
MAP_FRESH = timedelta(days=8)
CASE_STALE = timedelta(days=7)
# F1 checks that are safeguards for personal data on PCs, and the share of PCs that should pass.
SAFEGUARDS = (("bitlocker", "Personal data on PCs is encrypted", "BitLocker on the system drive", 0.9),
              ("defender", "PCs have working antivirus", "Microsoft Defender running", 0.9),
              ("firewall", "PCs have a working firewall", "Windows Firewall running", 0.9),
              ("patch", "PCs get security updates", "Windows updates installed", 0.8))


def _item(key, title, why, done, detail, link):
    return {"key": key, "title": title, "why": why, "status": "done" if done else "todo", "detail": detail,
            "link": link}


async def readiness(session: AsyncSession, org_id) -> dict:
    now = utcnow()
    row = await browser_policy.get(session, org_id)
    p = BrowserPolicyBody(**row.policy) if row else BrowserPolicyBody()
    items: list[dict] = []

    # 1. Know where personal data is kept.
    disc = await guard_discovery.for_org(session, org_id)
    last = await session.scalar(select(func.max(GuardDiscovery.scanned_at)).where(GuardDiscovery.org_id == org_id))
    fresh = p.discovery_enabled and last is not None and now - as_utc(last) <= MAP_FRESH
    items.append(_item(
        "data_map", "You know where personal data is kept",
        "You cannot protect, answer a request about, or report a breach of data you cannot find.", fresh,
        f"{disc['files_with_findings']:,} files with personal data on {disc['pcs']} PCs, checked weekly." if fresh
        else "Turn on the weekly check of where sensitive files are kept." if not p.discovery_enabled
        else "The weekly check has not reported in the last week.", "/guard/discovery"))

    # 2-5. Safeguards on the PCs, from the security checks.
    rows = await ComplianceService(session).evaluate_all(org_id=org_id)
    for key, title, label, share in SAFEGUARDS:
        results = [c.status for r in rows for c in r.checks if c.key == key and c.status in ("pass", "fail")]
        passed = sum(1 for s in results if s == "pass")
        ok = bool(results) and passed >= share * len(results)
        items.append(_item(key, title, "Reasonable security safeguards are expected for personal data.", ok,
                           f"{label}: {passed} of {len(results)} PCs." if results else "No PC has reported this yet.",
                           "/compliance"))

    # 6. Data leaving through the browser is checked.
    extension = (p.chrome_extension_id or p.edge_extension_id or p.firefox_extension_id) is not None
    acting = extension and p.guard_mode != "log"
    items.append(_item(
        "dlp", "Personal data leaving through the browser is checked",
        "Most leaks are a paste or an upload to a personal site or an AI chat.", acting,
        "The SAVIO extension is in place and acts on what it finds." if acting
        else "The extension only records so far (choose a mode in the browser policy)." if extension
        else "The SAVIO extension is not set up yet.", "/guard"))

    # 7. USB drives.
    usb = p.usb_mode != "off" or p.usb_observe
    items.append(_item("usb", "Copying to USB drives is controlled",
                       "A pendrive is the easiest way for a client list to leave the office.", usb,
                       "USB drives are controlled or recorded." if usb else "USB drives are left as they are.", "/guard"))

    # 8. Company accounts only.
    accounts = bool(p.google_allowed_domains or p.microsoft_tenant_id or p.claude_org_ids or p.chatgpt_workspace_ids
                    or p.slack_requester_id)
    items.append(_item("accounts", "Work data stays in company accounts",
                       "Data in a personal Google, Microsoft or ChatGPT account is out of your control.", accounts,
                       "Sign-in is limited to your organisation's accounts." if accounts
                       else "People can sign in to personal accounts at work.", "/guard"))

    # 9. Cases are looked at.
    stale = await session.scalar(select(func.count()).select_from(GuardCase).where(
        GuardCase.org_id == org_id, GuardCase.status == "open", GuardCase.level == "high",
        GuardCase.opened_at <= now - CASE_STALE))
    items.append(_item("cases", "High-risk cases are looked at within a week",
                       "A possible leak that nobody looks at cannot be stopped or reported in time.", not stale,
                       "No high-risk case has waited over a week." if not stale
                       else f"{stale} high-risk case(s) open for over a week.", "/guard/cases"))

    # 10. A named contact.
    settings = await SettingsService(session).ensure(org_id)
    contact = bool(settings.privacy_contact_name and settings.privacy_contact_email)
    items.append(_item("contact", "Someone is named for privacy complaints and breaches",
                       "People need someone to complain to, and a breach needs an owner from the first hour.", contact,
                       f"{settings.privacy_contact_name} ({settings.privacy_contact_email})." if contact
                       else "Name the person below.", "/guard/dpdp"))

    # 11. A record of who did what.
    items.append(_item("records", "Who did what is recorded",
                       "Showing what was done, and by whom, is part of answering for personal data.", True,
                       "SAVIO keeps an audit log of every change and action, and AI Guard's events for 180 days.",
                       "/audit"))

    done = sum(1 for i in items if i["status"] == "done")
    return {
        "score": round(100 * done / len(items)), "done": done, "total": len(items),
        "items": items, "map": await data_map(session, org_id, disc),
        "contact": {"name": settings.privacy_contact_name, "email": settings.privacy_contact_email},
        "disclaimer": DISCLAIMER, "generated_at": now,
    }


async def data_map(session: AsyncSession, org_id, disc: dict) -> dict:
    """Where personal data is kept and where it goes, by kind, in counts (30 days)."""
    since = utcnow() - timedelta(days=30)
    s = await guard_events.summary(session, org_id, 30)
    known = await guard_sites.learned(session)
    goes: dict[str, int] = {}
    for site, n in (await session.execute(select(GuardEvent.site, func.count()).where(
            GuardEvent.org_id == org_id, GuardEvent.occurred_at >= since).group_by(GuardEvent.site))).all():
        kind = "usb" if site == "usb" else guard_sites.kind_of(site, known)[0] or "other"
        goes[kind] = goes.get(kind, 0) + n
    return {
        "on_pcs": {"pcs": disc["pcs"], "files": disc["files_with_findings"], "contact_lists": disc["contact_lists"],
                   "kinds": disc["kinds"]},
        "leaving": {"events": s["total"], "kinds": s["kinds"], "where": dict(sorted(goes.items(), key=lambda kv: -kv[1]))},
    }


async def set_contact(session: AsyncSession, *, actor: User, name: str | None, email: str | None) -> None:
    settings = await SettingsService(session).ensure(actor.org_id)
    settings.privacy_contact_name, settings.privacy_contact_email = name, email
    await AuditService(session).record(
        org_id=actor.org_id, actor_id=actor.id, action="dpdp.contact_update", target_type="organization",
        target_id=str(actor.org_id), detail={"name": name, "email": email},
    )
    await session.commit()
