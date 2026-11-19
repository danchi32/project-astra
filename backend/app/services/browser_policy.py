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
    AuditLog,
    Device,
    DeviceBrowserPolicyState,
    DeviceGroup,
    DeviceGroupMember,
    GroupBrowserPolicy,
    GuardUsbWindow,
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

# D10: browsers SAVIO's policies and extension do not reach. Each name is the agent's own
# (OtherBrowsers.cs), with the installed-app name it is recognised by in telemetry. Supported
# browsers are Chrome, Edge and Firefox.
# ponytail: a fixed list in code, kept in step with the agent's. Upgrade path is serving the list
# with the policy once someone needs one that is not here.
OTHER_BROWSERS: dict[str, str] = {   # name → how its installed-app name starts (lower case)
    "Brave": "brave", "Opera": "opera", "Vivaldi": "vivaldi", "Yandex Browser": "yandex",
    "Tor Browser": "tor browser", "Chromium": "chromium", "Waterfox": "waterfox", "LibreWolf": "librewolf",
}
UsbMode = Literal["off", "read_only", "encrypted_only", "on_request", "block", "company_drives"]
# C3b: a USB disk's Windows device instance ID, as the agent reports it. Never SCSI\ (internal disks).
_DRIVE_ID = re.compile(r"^USBSTOR\\[A-Za-z0-9&_.\-]{1,200}\\[A-Za-z0-9&_.\-]{1,100}$")
MAX_APPROVED_DRIVES = 100


class ApprovedDrive(BaseModel):
    """C3b: a company drive, approved by an admin, with the name they gave it."""
    model_config = ConfigDict(extra="forbid")
    id: str = Field(max_length=310)
    name: str = Field(min_length=1, max_length=60)

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not _DRIVE_ID.match(v):
            raise ValueError("Not a USB drive's device ID")
        # A drive without its own serial gets an ID Windows makes up ("…\7&1a2b3c4d&0"): every
        # drive of that model in that port shares it. The agent refuses it too (review 3b L2).
        if v.rsplit("\\", 1)[1][1:2] == "&":
            raise ValueError("This drive has no serial number of its own, so it cannot be approved by itself")
        return v

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v or has_control(v):
            raise ValueError("A drive's name must be plain text")
        return v
USB_WINDOW_MINUTES = (15, 480)   # shortest and longest write window IT can open
OtherBrowser = Literal["Brave", "Opera", "Vivaldi", "Yandex Browser", "Tor Browser", "Chromium", "Waterfox",
                       "LibreWolf"]


def other_browsers(app_names) -> list[str]:
    """Which of OTHER_BROWSERS a PC's installed applications include ("Opera GX Stable", not "Operations")."""
    names = [(n or "").lower() for n in app_names]
    return [b for b, p in OTHER_BROWSERS.items() if any(re.match(rf"{re.escape(p)}\b", n) for n in names)]


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
    # D3/D5: also read the text inside PDFs, for uploads and the weekly map, on the PC (Word and
    # Excel are read either way). Off: a PDF is "could not check". The admin's choice.
    guard_read_pdfs: bool = False
    # D2 beyond Google: sign-in only to the org's own Microsoft tenant, Claude organizations,
    # ChatGPT workspaces and Slack workspaces. Each service enforces it itself when its header
    # arrives; the extension adds the header (as a proxy would), so these need the extension.
    microsoft_tenant_id: str | None = None
    microsoft_policy_id: str | None = None      # Entra's tenant-restrictions policy ID
    # The same two IDs in Windows' own tenant restrictions v2 on each PC, so Office apps (Outlook,
    # Teams, Word…) and Edge enforce them too. Needs no extension. Off by default: a wrong ID stops
    # Office signing in on every PC that gets it.
    microsoft_on_windows: bool = False
    claude_org_ids: list[str] = Field(default_factory=list, max_length=MAX_ACCOUNT_IDS)
    chatgpt_workspace_ids: list[str] = Field(default_factory=list, max_length=MAX_ACCOUNT_IDS)
    slack_requester_id: str | None = None       # the org's own workspace or org ID
    slack_allowed_ids: list[str] = Field(default_factory=list, max_length=MAX_ACCOUNT_IDS)
    # D10: the agent closes any of OTHER_BROWSERS as it starts, and tells the person why. Removing
    # one stays the admin-only "Uninstall software" action, PC by PC.
    block_other_browsers: bool = False
    # C3: USB drives and phones, through Windows' own policies. off (SAVIO leaves them alone) ·
    # read_only · encrypted_only (BitLocker To Go drives only) · on_request (read-only, except in
    # a write window IT opens for one PC) · block.
    usb_mode: UsbMode = "off"
    # C3b: record what is copied onto USB drives, in counts, checked on the PC by the scanner that
    # has no network. Independent of usb_mode; off by default.
    usb_observe: bool = False
    # C3b: in company_drives mode, the only USB drives that work; every other one is not installed.
    usb_approved_drives: list[ApprovedDrive] = Field(default_factory=list, max_length=MAX_APPROVED_DRIVES)

    @field_validator("usb_approved_drives")
    @classmethod
    def _drives(cls, v: list[ApprovedDrive]) -> list[ApprovedDrive]:
        seen: dict[str, ApprovedDrive] = {}
        for d in v:
            seen.setdefault(d.id.upper(), d)
        return list(seen.values())

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
        if self.microsoft_on_windows and self.microsoft_tenant_id is None:
            raise ValueError("Microsoft 365 on the PC needs the tenant ID and the tenant restrictions policy ID")
        # Windows enforces the Microsoft IDs itself when asked to; everything else needs the extension.
        accounts = ((self.microsoft_tenant_id and not self.microsoft_on_windows) or self.claude_org_ids
                    or self.chatgpt_workspace_ids or self.slack_requester_id)
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
    # Nor is "Windows": it is Windows' own tenant restrictions (D2 on the PC). "Usb" and
    # "UsbEncryption" are Windows' removable-storage and BitLocker To Go policies (C3).
    browser: Literal["Chrome", "Edge", "Firefox", "Scanner", "Windows", "Usb", "UsbEncryption", "UsbDevices"]
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


class SeenDrive(BaseModel):
    """C3b: a USB drive Windows has installed on the reporting PC."""
    model_config = ConfigDict(extra="forbid")
    id: str = Field(max_length=310)
    name: str = Field(max_length=100)
    unique_serial: bool = True

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not _DRIVE_ID.match(v):
            raise ValueError("Not a USB drive's device ID")
        return v

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        # Device-supplied and shown to admins: control and invisible characters go.
        return "".join(ch for ch in v if not unicodedata.category(ch).startswith("C")).strip() or "USB drive"


class BrowserPolicyReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=0)
    results: list[BrowserResult] = Field(max_length=10)
    drives: list[SeenDrive] = Field(default_factory=list, max_length=50)
    # D10: how many times each other browser was closed since the last report. Only known names.
    closed: dict[OtherBrowser, int] = Field(default_factory=dict)

    @field_validator("closed")
    @classmethod
    def _closed(cls, v: dict[str, int]) -> dict[str, int]:
        return {k: min(n, 10_000) for k, n in v.items() if n > 0}


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


def _check_pilot(org: OrgBrowserPolicy | None, body: BrowserPolicyBody) -> None:
    # E8: the first 14 days only record, so the org sees what happens before anyone is
    # interrupted. Enforced here, under the policy page, group policies and suggestions alike.
    # Nothing switches on by itself when the pilot ends: an admin picks the mode.
    if body.guard_mode != "log" and (until := pilot_until(org)) is not None:
        raise PilotActive(f"AI Guard only records until {as_utc(until):%d %b %Y}, its 14-day pilot. "
                          "End the pilot first to choose another mode.")


def _save(row, org: OrgBrowserPolicy, body: BrowserPolicyBody, actor: User) -> list[str]:
    """Write `body` into a policy row (the org's or a group's). A real change takes the org's
    next version number. Returns the fields that changed."""
    new = body.model_dump()
    hosts = category_hosts(body.blocked_categories)
    changed = sorted(k for k in new if (row.policy or {}).get(k) != new[k])
    if row.category_hosts != hosts:
        changed.append("category_hosts")   # same categories, list updated since: a new version too
    if changed:
        org.seq += 1
        row.policy, row.version, row.updated_by_user_id, row.category_hosts = new, org.seq, actor.id, hosts
    return changed


async def put(session: AsyncSession, *, actor: User, body: BrowserPolicyBody) -> OrgBrowserPolicy:
    row = await session.get(OrgBrowserPolicy, actor.org_id)
    _check_pilot(row, body)
    if row is None:
        hosts = category_hosts(body.blocked_categories)
        row = OrgBrowserPolicy(org_id=actor.org_id, policy=body.model_dump(), version=1, seq=1,
                               updated_by_user_id=actor.id, pilot_until=utcnow() + PILOT, category_hosts=hosts)
        session.add(row)
        changed = sorted(row.policy)
    else:
        changed = _save(row, row, body, actor)
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


# ── D1: a group's own policy ────────────────────────────────────────────────────────────────

class NoOrgPolicy(ValueError):
    """Group policies start from, and fall back to, the org's policy: it must exist first."""


async def group_policies(session: AsyncSession, org_id) -> list[tuple[GroupBrowserPolicy, str]]:
    """The org's group policies with their group names, in the order they win."""
    return list((await session.execute(
        select(GroupBrowserPolicy, DeviceGroup.name)
        .join(DeviceGroup, DeviceGroup.id == GroupBrowserPolicy.group_id)
        .where(GroupBrowserPolicy.org_id == org_id)
        .order_by(GroupBrowserPolicy.priority, DeviceGroup.name)
    )).all())


async def put_group(session: AsyncSession, *, actor: User, group_id, priority: int,
                    body: BrowserPolicyBody) -> GroupBrowserPolicy:
    group = await session.get(DeviceGroup, group_id)
    if group is None or group.org_id != actor.org_id:
        raise LookupError("No such group.")
    org = await session.get(OrgBrowserPolicy, actor.org_id)
    if org is None:
        raise NoOrgPolicy("Save the policy for everyone first; groups start from it.")
    _check_pilot(org, body)
    row = await session.get(GroupBrowserPolicy, group_id)
    if row is None:
        org.seq += 1
        row = GroupBrowserPolicy(group_id=group_id, org_id=actor.org_id, priority=priority, policy=body.model_dump(),
                                 version=org.seq, category_hosts=category_hosts(body.blocked_categories),
                                 updated_by_user_id=actor.id)
        session.add(row)
        changed = sorted(row.policy)
    else:
        changed = _save(row, org, body, actor)
    if row.priority != priority:
        # Which policy a PC gets may change; its version already names the content, so no new one.
        row.priority = priority
        changed.append("priority")
    await AuditService(session).record(
        org_id=actor.org_id, actor_id=actor.id, action="guard.group_policy_update",
        target_type="device_group", target_id=str(group_id),
        detail={"group": group.name, "changed": changed, "version": row.version, "priority": row.priority},
    )
    await session.commit()
    return row


async def delete_group(session: AsyncSession, *, actor: User, group_id) -> None:
    """The group's PCs go back to the org's policy (a different version, so an update)."""
    row = await session.get(GroupBrowserPolicy, group_id)
    if row is None or row.org_id != actor.org_id:
        raise LookupError("That group has no policy of its own.")
    group = await session.get(DeviceGroup, group_id)
    await AuditService(session).record(
        org_id=actor.org_id, actor_id=actor.id, action="guard.group_policy_delete",
        target_type="device_group", target_id=str(group_id), detail={"group": group.name if group else None},
    )
    await session.delete(row)
    await session.commit()


async def applies_to(session: AsyncSession, org_id, device_ids) -> dict:
    """Device id → (group name, its policy) for PCs a group policy covers; others get the org's."""
    ranked = await group_policies(session, org_id)
    if not ranked or not device_ids:
        return {}
    members = (await session.execute(
        select(DeviceGroupMember.group_id, DeviceGroupMember.device_id)
        .where(DeviceGroupMember.group_id.in_([g.group_id for g, _ in ranked]),
               DeviceGroupMember.device_id.in_(list(device_ids)))
    )).all()
    by_group: dict = {}
    for gid, did in members:
        by_group.setdefault(gid, set()).add(did)
    out: dict = {}
    for g, name in ranked:                          # first match wins: lowest priority, then name
        for did in by_group.get(g.group_id, ()):
            out.setdefault(did, (name, g))
    return out


async def for_device(session: AsyncSession, device: Device) -> dict:
    """What a PC should apply: its group's policy if one covers it, else the org's. An org
    without the add-on gets an empty policy at version 0, which tells the agent to remove
    everything SAVIO set."""
    if not await entitled(session, device.org_id):
        return {"version": 0, "policy": {}}
    row = await session.get(OrgBrowserPolicy, device.org_id)
    if row is None:
        return {"version": 0, "policy": {}}
    if (hit := (await applies_to(session, device.org_id, {device.id})).get(device.id)) is not None:
        row = hit[1]
    # D1: the PC gets one block list; categories are the portal's way of choosing it.
    policy = {k: v for k, v in row.policy.items() if k != "blocked_categories"}
    policy["blocked_sites"] = list(dict.fromkeys([*policy.get("blocked_sites", []), *(row.category_hosts or [])]))
    return {"version": row.version, "policy": policy}


# ── C3: USB write windows ───────────────────────────────────────────────────────────────────

class NotOnRequest(ValueError):
    """A write window only means something on a PC whose policy is "write on request"."""


async def usb_window(session: AsyncSession, device: Device) -> datetime | None:
    """When this PC may write to USB drives until, if IT opened a window and its policy still asks."""
    row = await session.get(GuardUsbWindow, device.id)
    if row is None or as_utc(row.until) <= utcnow():
        return None
    return row.until if (await for_device(session, device))["policy"].get("usb_mode") == "on_request" else None


async def open_usb_window(session: AsyncSession, *, actor: User, device_id, minutes: int) -> GuardUsbWindow:
    device = await session.get(Device, device_id)
    if device is None or device.org_id != actor.org_id:
        raise LookupError("No such PC.")
    if (await for_device(session, device))["policy"].get("usb_mode") != "on_request":
        raise NotOnRequest(f"{device.hostname} is not in 'write on request' mode, so there is nothing to open.")
    row = await session.get(GuardUsbWindow, device.id)
    until = utcnow() + timedelta(minutes=minutes)
    if row is None:
        row = GuardUsbWindow(device_id=device.id, org_id=device.org_id, until=until)
        session.add(row)
    row.until, row.opened_by_user_id, row.opened_at = until, actor.id, utcnow()
    await AuditService(session).record(
        org_id=actor.org_id, actor_id=actor.id, action="guard.usb_window_open", target_type="device",
        target_id=str(device.id), detail={"device": device.hostname, "minutes": minutes},
    )
    await session.commit()
    return row


async def close_usb_window(session: AsyncSession, *, actor: User, device_id) -> None:
    row = await session.get(GuardUsbWindow, device_id)
    if row is None or row.org_id != actor.org_id:
        raise LookupError("No window is open on that PC.")
    device = await session.get(Device, device_id)
    await session.delete(row)
    await AuditService(session).record(
        org_id=actor.org_id, actor_id=actor.id, action="guard.usb_window_close", target_type="device",
        target_id=str(device_id), detail={"device": device.hostname if device else None},
    )
    await session.commit()


async def usb_windows(session: AsyncSession, org_id) -> dict:
    """Device id → until, for windows still open."""
    rows = (await session.execute(select(GuardUsbWindow).where(GuardUsbWindow.org_id == org_id))).scalars()
    return {r.device_id: r.until for r in rows if as_utc(r.until) > utcnow()}


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
    drives = [d.model_dump() for d in report.drives]
    if state is None:
        state = DeviceBrowserPolicyState(device_id=device.id, org_id=device.org_id, version=report.version,
                                         results=results, reported_at=utcnow(), drives=drives)
        session.add(state)
    else:
        state.version, state.results, state.reported_at, state.drives = report.version, results, utcnow(), drives
    # At most one audit row per PC an hour for closed browsers: a device must not be able to push
    # real entries off the audit log's first pages (security review 3b L5).
    if report.closed and not (await session.execute(select(func.count()).select_from(AuditLog).where(
            AuditLog.org_id == device.org_id, AuditLog.action == "guard.other_browser_closed",
            AuditLog.target_id == str(device.id), AuditLog.created_at >= utcnow() - TAMPER_NOTIFY_EVERY))).scalar_one():
        await AuditService(session).record(
            org_id=device.org_id, actor_id=None, action="guard.other_browser_closed",
            target_type="device", target_id=str(device.id),
            detail={"device": device.hostname, "closed": report.closed},
        )
    repaired =sorted({f"{r.browser}: {n}" for r in report.results for n in r.repaired})
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


async def drives_seen(session: AsyncSession, org_id) -> list[dict]:
    """C3b: every USB drive the org's PCs reported, with where it was seen and which policies
    already approve it, so an admin can approve the company's own."""
    approved: dict[str, list[str]] = {}
    org = await session.get(OrgBrowserPolicy, org_id)
    for scope, row in [("Everyone", org)] + [(name, g) for g, name in await group_policies(session, org_id)]:
        for d in ((row.policy if row else None) or {}).get("usb_approved_drives", []):
            approved.setdefault(d["id"].upper(), []).append(scope)
    seen: dict[str, dict] = {}
    for state, host in await device_states(session, org_id):
        for d in state.drives or []:
            entry = seen.setdefault(d["id"].upper(), {**d, "pcs": [], "last_seen": state.reported_at})
            if host not in entry["pcs"]:
                entry["pcs"].append(host)
            entry["last_seen"] = max(entry["last_seen"], state.reported_at)
    for key, entry in seen.items():
        entry["approved_in"] = approved.get(key, [])
    return sorted(seen.values(), key=lambda e: (bool(e["approved_in"]), e["name"].lower()))


async def device_states(session: AsyncSession, org_id) -> list[tuple[DeviceBrowserPolicyState, str]]:
    return list((await session.execute(
        select(DeviceBrowserPolicyState, Device.hostname)
        .join(Device, Device.id == DeviceBrowserPolicyState.device_id)
        .where(DeviceBrowserPolicyState.org_id == org_id)
        .order_by(Device.hostname)
    )).all())
