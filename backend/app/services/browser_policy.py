"""Phase 3 · D10: the org's browser lock-down, served to its PCs, and what each PC reports back.

The agent applies the policy with `BrowserPolicyWriter`, which owns only what it wrote: a
policy the org already sets some other way is reported as a conflict, not overwritten. This
service stores the policy, hands it to entitled PCs, and keeps each PC's last report.
- A PC repairing a SAVIO policy someone removed (drift) raises a notification.
- An org without `ai_guard` serves its PCs an empty policy, so turning the add-on off removes
  every setting SAVIO made.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Device,
    DeviceBrowserPolicyState,
    Notification,
    NotificationCategory,
    NotificationSeverity,
    Organization,
    OrgBrowserPolicy,
    User,
)
from app.models.base import as_utc, utcnow
from app.services.audit import AuditService
from app.services.entitlements import AI_GUARD, features_for
from app.services.notifications import NotificationService

MAX_SITES = 500
MAX_KEYWORDS = 200
# The scanner's finding names (AstraAgent.Guard.Finding), which the extension sees in its counts.
FINDING_KINDS = ("Aadhaar", "Pan", "Gstin", "PaymentCard", "IndianMobile", "Email", "BankAccount")
FindingKind = Literal["Aadhaar", "Pan", "Gstin", "PaymentCard", "IndianMobile", "Email", "BankAccount"]
_HOST = re.compile(r"^(?=.{1,253}$)(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$")
_CHROMIUM_ID = re.compile(r"^[a-p]{32}$")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_SLACK_ID = re.compile(r"^[TE][A-Z0-9]{6,20}$")
MAX_ACCOUNT_IDS = 50
_FIREFOX_ID = re.compile(r"^(\{[0-9a-fA-F-]{36}\}|[A-Za-z0-9._-]{1,80}@[A-Za-z0-9.-]{1,80})$")
# Where a forced Firefox extension may come from (security review L4): Mozilla's own store. A
# self-hosted .xpi host is added here, in code, when there is one.
FIREFOX_EXTENSION_HOSTS = ("addons.mozilla.org",)
# Names an agent may report: policy names, 3rdparty paths, extension IDs, firewall rule names.
_REPORT_NAME = re.compile(r"^[A-Za-z0-9_.@\\{}: -]{1,100}$")
TAMPER_NOTIFY_EVERY = timedelta(hours=1)
PILOT = timedelta(days=14)   # E8

# D1: sites to block by kind instead of one by one. A host covers its subdomains, so these name
# the personal service, never a shared parent a business also uses (outlook.live.com, not
# live.com; web.whatsapp.com, not whatsapp.com; no Gmail or Drive, which D2's Google domains
# handle). The hosts are copied into the policy when it is saved (`category_hosts`), so a PC is
# only ever served what an admin saved.
# ponytail: a fixed list in code. Upgrade path is a maintained category feed (or the browser's
# own categories) once an org needs more than these.
SITE_CATEGORIES: dict[str, tuple[str, tuple[str, ...]]] = {
    "file_sharing": ("Personal file-sharing", (
        "wetransfer.com", "we.tl", "file.io", "gofile.io", "send-anywhere.com", "sendanywhere.com",
        "filemail.com", "mega.nz", "mediafire.com", "fromsmash.com", "transfernow.net", "swisstransfer.com")),
    "personal_email": ("Personal e-mail", (
        "mail.yahoo.com", "outlook.live.com", "mail.proton.me", "mail.aol.com", "gmx.com", "gmx.net",
        "mail.com", "tuta.com", "rediffmail.com")),
    "ai_chat": ("AI chat", (
        "chatgpt.com", "chat.openai.com", "claude.ai", "gemini.google.com", "copilot.microsoft.com",
        "perplexity.ai", "chat.deepseek.com", "meta.ai")),
    "messaging": ("Messaging on the web", (
        "web.whatsapp.com", "web.telegram.org", "discord.com", "messenger.com")),
    "social_media": ("Social media", (
        "facebook.com", "instagram.com", "x.com", "twitter.com", "threads.net", "snapchat.com", "reddit.com",
        "pinterest.com", "tumblr.com", "sharechat.com")),
    "paste_sites": ("Paste sites", (
        "pastebin.com", "paste.ee", "hastebin.com", "justpaste.it", "controlc.com", "rentry.co", "dpaste.org",
        "privatebin.net")),
}
SiteCategory = Literal["file_sharing", "personal_email", "ai_chat", "messaging", "social_media", "paste_sites"]


def category_hosts(categories: list[str]) -> list[str]:
    return list(dict.fromkeys(h for c in categories for h in SITE_CATEGORIES[c][1]))


def _slack_ids(v: list[str]) -> list[str]:
    out = [x.strip().upper() for x in v if x and x.strip()]
    if bad := next((x for x in out if not _SLACK_ID.match(x)), None):
        raise ValueError(f"'{bad[:60]}' is not a Slack workspace or org ID (like T0123ABCD or E0123ABCD)")
    return list(dict.fromkeys(out))


def has_control(s: str) -> bool:
    """Any control, format (bidi overrides, zero-width), private-use or unassigned character.
    Text from a device or an admin that ends up on screens is refused if it has one."""
    return any(unicodedata.category(ch).startswith("C") for ch in s)


class BrowserPolicyBody(BaseModel):
    """The same rules the agent's `BrowserPolicy.Validate` applies, checked here first, so a
    policy the agent would refuse is never saved. Unknown fields are refused."""
    model_config = ConfigDict(extra="forbid")

    incognito_off: bool = False
    extension_developer_mode_off: bool = False
    dev_tools_off: bool = False
    new_profiles_off: bool = False
    blocked_sites: list[str] = Field(default_factory=list, max_length=MAX_SITES)
    # D1: whole kinds of site, on top of `blocked_sites`. `allowed_sites` still wins.
    blocked_categories: list[SiteCategory] = Field(default_factory=list, max_length=len(SITE_CATEGORIES))
    allowed_sites: list[str] = Field(default_factory=list, max_length=MAX_SITES)
    google_allowed_domains: list[str] = Field(default_factory=list, max_length=MAX_SITES)
    chrome_extension_id: str | None = None
    edge_extension_id: str | None = None
    firefox_extension_id: str | None = None
    firefox_extension_url: str | None = Field(default=None, max_length=500)
    # "store": the extension is force-installed from the browser's store (the normal case).
    # "manual": IT installs it by hand (a pilot before the store listing, or testing): no
    # force-install entry, because a browser refuses a hand-installed copy of a force-listed
    # ID; the extension's settings and its native host are set up exactly as for "store".
    extension_install: Literal["store", "manual"] = "store"
    # D3: the extension's own settings, handed to it as managed policy where it is forced in.
    guard_mode: Literal["log", "warn", "justify", "redact", "approve", "block"] = "log"
    guard_watched_sites: list[str] = Field(default_factory=list, max_length=MAX_SITES)
    guard_ignore_kinds: list[FindingKind] = Field(default_factory=lambda: ["Email"], max_length=len(FINDING_KINDS))
    guard_keywords: list[str] = Field(default_factory=list, max_length=MAX_KEYWORDS)
    # D5: weekly scan of each person's Desktop / Documents / Downloads / OneDrive, on the PC, for
    # a map of which folders hold sensitive files (counts only). Off until an admin turns it on.
    discovery_enabled: bool = False
    # D2 beyond Google: sign-in only to the org's own Microsoft tenant, Claude organizations,
    # ChatGPT workspaces and Slack workspaces. Each service enforces it itself when its header
    # arrives; the extension adds the header (as a proxy would), so these need the extension.
    microsoft_tenant_id: str | None = None
    microsoft_policy_id: str | None = None      # Entra's tenant-restrictions policy ID
    claude_org_ids: list[str] = Field(default_factory=list, max_length=MAX_ACCOUNT_IDS)
    chatgpt_workspace_ids: list[str] = Field(default_factory=list, max_length=MAX_ACCOUNT_IDS)
    slack_requester_id: str | None = None       # the org's own workspace or org ID
    slack_allowed_ids: list[str] = Field(default_factory=list, max_length=MAX_ACCOUNT_IDS)

    @field_validator("microsoft_tenant_id", "microsoft_policy_id")
    @classmethod
    def _uuid(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        if not _UUID.match(v := v.strip().lower()):
            raise ValueError("Must be an ID like aaaabbbb-0000-cccc-1111-dddd2222eeee")
        return v

    @field_validator("claude_org_ids", "chatgpt_workspace_ids")
    @classmethod
    def _uuids(cls, v: list[str]) -> list[str]:
        out = [x.strip().lower() for x in v if x and x.strip()]
        if bad := next((x for x in out if not _UUID.match(x)), None):
            raise ValueError(f"'{bad[:60]}' is not an ID like aaaabbbb-0000-cccc-1111-dddd2222eeee")
        return list(dict.fromkeys(out))

    @field_validator("slack_requester_id")
    @classmethod
    def _slack_one(cls, v: str | None) -> str | None:
        return (_slack_ids([v or ""]) or [None])[0]

    @field_validator("slack_allowed_ids")
    @classmethod
    def _slack(cls, v: list[str]) -> list[str]:
        return _slack_ids(v)

    @field_validator("guard_ignore_kinds", "blocked_categories")
    @classmethod
    def _kinds(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(v))

    @field_validator("guard_keywords")
    @classmethod
    def _keywords(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for raw in v:
            kw = (raw or "").strip()
            if not 1 <= len(kw) <= 100:
                raise ValueError("Keywords must be 1–100 characters")
            if has_control(kw):
                raise ValueError("Keywords cannot contain control or invisible characters")
            if kw.lower() not in (o.lower() for o in out):
                out.append(kw)
        return out

    @field_validator("blocked_sites", "allowed_sites", "google_allowed_domains", "guard_watched_sites")
    @classmethod
    def _hosts(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for raw in v:
            host = (raw or "").strip().lower().removeprefix("https://").removeprefix("http://").rstrip("/")
            if not _HOST.match(host):
                raise ValueError(f"'{raw[:60]}' is not a host name (like example.com)")
            if host not in out:
                out.append(host)
        return out

    @model_validator(mode="after")
    def _extension(self) -> BrowserPolicyBody:
        # The PC gets one block list, and refuses one over its limit.
        if len(set(self.blocked_sites) | set(category_hosts(self.blocked_categories))) > MAX_SITES:
            raise ValueError(f"Blocked sites and categories together come to more than {MAX_SITES} sites")
        for name, rx in (("chrome_extension_id", _CHROMIUM_ID), ("edge_extension_id", _CHROMIUM_ID),
                         ("firefox_extension_id", _FIREFOX_ID)):
            value = getattr(self, name)
            if value is not None and not rx.match(value):
                raise ValueError(f"{name} is malformed")
        if self.extension_install == "manual":
            if self.firefox_extension_url is not None:
                raise ValueError("A manually installed extension has no install URL")
            if self.extension_developer_mode_off:
                raise ValueError("Installing the extension by hand needs extension developer mode: "
                                 "turn off 'No extension developer mode' while it is manual")
        elif (self.firefox_extension_id is None) != (self.firefox_extension_url is None):
            raise ValueError("A Firefox extension needs both an ID and an install URL")
        if (self.microsoft_tenant_id is None) != (self.microsoft_policy_id is None):
            raise ValueError("Microsoft 365 needs both the tenant ID and the tenant restrictions policy ID")
        if (self.slack_requester_id is None) != (not self.slack_allowed_ids):
            raise ValueError("Slack needs your own workspace or org ID and the list of allowed IDs")
        accounts = (self.microsoft_tenant_id or self.claude_org_ids or self.chatgpt_workspace_ids
                    or self.slack_requester_id)
        if accounts and not (self.chrome_extension_id or self.edge_extension_id or self.firefox_extension_id):
            raise ValueError("Company-account-only sign-in for these services works through the SAVIO "
                             "extension: set its ID first")
        if self.firefox_extension_url and not self.firefox_extension_url.startswith("https://"):
            raise ValueError("The Firefox extension URL must be https")
        if self.firefox_extension_url:
            host = self.firefox_extension_url.removeprefix("https://").split("/", 1)[0].lower()
            if host not in FIREFOX_EXTENSION_HOSTS:
                raise ValueError(f"The Firefox extension must come from {', '.join(FIREFOX_EXTENSION_HOSTS)}")
        return self


class BrowserResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # "Scanner" is not a browser: it is E4's firewall block on the extension's native host.
    browser: Literal["Chrome", "Edge", "Firefox", "Scanner"]
    set: list[str] = Field(default_factory=list, max_length=50)
    repaired: list[str] = Field(default_factory=list, max_length=50)
    removed: list[str] = Field(default_factory=list, max_length=50)
    conflicts: list[str] = Field(default_factory=list, max_length=50)
    error: str | None = Field(default=None, max_length=500)

    @field_validator("set", "repaired", "removed", "conflicts")
    @classmethod
    def _names(cls, v: list[str]) -> list[str]:
        # Device-supplied, shown to staff and named in notifications: names only, never prose.
        return [n for n in v if _REPORT_NAME.match(n)]

    @field_validator("error")
    @classmethod
    def _error(cls, v: str | None) -> str | None:
        return None if v is None else "".join(ch for ch in v if not unicodedata.category(ch).startswith("C"))


class BrowserPolicyReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=0)
    results: list[BrowserResult] = Field(max_length=10)


async def entitled(session: AsyncSession, org_id) -> bool:
    org = await session.get(Organization, org_id)
    return org is not None and AI_GUARD in features_for(org.plan, org.entitlement_overrides)


async def get(session: AsyncSession, org_id) -> OrgBrowserPolicy | None:
    return await session.get(OrgBrowserPolicy, org_id)


class PilotActive(ValueError):
    """E8: a mode other than record-only was asked for during the pilot."""


def pilot_until(row: OrgBrowserPolicy | None) -> datetime | None:
    """When the pilot ends, if it is still running. A new org (no policy yet) is about to
    start one, so its first save is held to record-only as well."""
    if row is None:
        return utcnow() + PILOT
    return row.pilot_until if row.pilot_until is not None and as_utc(row.pilot_until) > utcnow() else None


async def put(session: AsyncSession, *, actor: User, body: BrowserPolicyBody) -> OrgBrowserPolicy:
    row = await session.get(OrgBrowserPolicy, actor.org_id)
    # E8: the first 14 days only record, so the org sees what happens before anyone is
    # interrupted. Enforced here, under the policy page and suggestions alike. Nothing switches
    # on by itself when the pilot ends: an admin picks the mode.
    if body.guard_mode != "log" and (until := pilot_until(row)) is not None:
        raise PilotActive(f"AI Guard only records until {as_utc(until):%d %b %Y}, its 14-day pilot. "
                          "End the pilot first to choose another mode.")
    new = body.model_dump()
    hosts = category_hosts(body.blocked_categories)
    before = row.policy if row else {}
    changed = sorted(k for k in new if before.get(k) != new[k])
    if row is not None and row.category_hosts != hosts:
        changed.append("category_hosts")   # same categories, list updated since: a new version too
    if row is None:
        row = OrgBrowserPolicy(org_id=actor.org_id, policy=new, version=1, updated_by_user_id=actor.id,
                               pilot_until=utcnow() + PILOT, category_hosts=hosts)
        session.add(row)
    elif changed:
        row.policy, row.version, row.updated_by_user_id, row.category_hosts = new, row.version + 1, actor.id, hosts
    await AuditService(session).record(
        org_id=actor.org_id, actor_id=actor.id, action="guard.browser_policy_update",
        target_type="organization", target_id=str(actor.org_id),
        detail={"changed": changed, "version": row.version},
    )
    await session.commit()
    return row


async def end_pilot(session: AsyncSession, *, actor: User) -> OrgBrowserPolicy:
    """E8: an admin chose not to wait the 14 days. Audited; the mode itself is still theirs to pick."""
    row = await session.get(OrgBrowserPolicy, actor.org_id)
    if row is None or pilot_until(row) is None:
        raise LookupError("There is no pilot running.")
    row.pilot_until = utcnow()
    await AuditService(session).record(
        org_id=actor.org_id, actor_id=actor.id, action="guard.pilot_end",
        target_type="organization", target_id=str(actor.org_id), detail={},
    )
    await session.commit()
    return row


async def for_device(session: AsyncSession, device: Device) -> dict:
    """What a PC should apply. An org without the add-on gets an empty policy at version 0,
    which tells the agent to remove everything SAVIO set."""
    if not await entitled(session, device.org_id):
        return {"version": 0, "policy": {}}
    row = await session.get(OrgBrowserPolicy, device.org_id)
    if row is None:
        return {"version": 0, "policy": {}}
    # D1: the PC gets one block list; categories are the portal's way of choosing it.
    policy = {k: v for k, v in row.policy.items() if k != "blocked_categories"}
    policy["blocked_sites"] = list(dict.fromkeys([*policy.get("blocked_sites", []), *(row.category_hosts or [])]))
    return {"version": row.version, "policy": policy}


async def record_report(session: AsyncSession, device: Device, report: BrowserPolicyReport) -> None:
    if not await entitled(session, device.org_id):
        return   # accepted and dropped, as the other AI Guard ingest paths do
    state = await session.get(DeviceBrowserPolicyState, device.id)
    if state is None or state.version != report.version:
        # The agent cannot tell a value someone changed from one the org changed: both differ
        # from what is wanted now. In the first report of a new version it is the org's update,
        # not tampering (live test: every mode change alerted the admin). The version is kept
        # here, so this holds across agent restarts. A planted user-level host is never the
        # org's doing and stays tampering.
        for r in report.results:
            update = [n for n in r.repaired if not n.startswith("user-level ")]
            r.set, r.repaired = r.set + update, [n for n in r.repaired if n.startswith("user-level ")]
    results = [r.model_dump() for r in report.results]
    if state is None:
        state = DeviceBrowserPolicyState(device_id=device.id, org_id=device.org_id, version=report.version,
                                         results=results, reported_at=utcnow())
        session.add(state)
    else:
        state.version, state.results, state.reported_at = report.version, results, utcnow()
    repaired = sorted({f"{r.browser}: {n}" for r in report.results for n in r.repaired})
    if repaired:
        # Someone on this PC removed or changed a lock SAVIO set. It is back on; the admin
        # should know it happened, and on which PC.
        await AuditService(session).record(
            org_id=device.org_id, actor_id=None, action="guard.browser_policy_tamper",
            target_type="device", target_id=str(device.id),
            detail={"device": device.hostname, "repaired": repaired[:20]},
        )
        # At most one notification per PC an hour: a device reporting repairs in a loop must not
        # flood every user's notification list (security review M1). The audit keeps them all.
        message = f"{device.hostname}: {', '.join(repaired[:5])} had been changed and was put back."
        recent = (await session.execute(select(func.count()).select_from(Notification).where(
            Notification.org_id == device.org_id, Notification.title == "Browser policy tampered",
            Notification.message.startswith(f"{device.hostname}: "),
            Notification.created_at >= utcnow() - TAMPER_NOTIFY_EVERY))).scalar_one()
        if recent == 0:
            await NotificationService(session).notify(
                org_id=device.org_id, category=NotificationCategory.SYSTEM,
                severity=NotificationSeverity.WARNING, title="Browser policy tampered",
                message=message, link="/guard",
            )
    await session.commit()


async def device_states(session: AsyncSession, org_id) -> list[tuple[DeviceBrowserPolicyState, str]]:
    return list((await session.execute(
        select(DeviceBrowserPolicyState, Device.hostname)
        .join(Device, Device.id == DeviceBrowserPolicyState.device_id)
        .where(DeviceBrowserPolicyState.org_id == org_id)
        .order_by(Device.hostname)
    )).all())
