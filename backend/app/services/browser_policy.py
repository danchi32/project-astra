"""Phase 3 · D10: the org's browser lock-down, served to its PCs, and what each PC reports back.

The agent applies the policy with `BrowserPolicyWriter`, which owns only what it wrote: a
policy the org already sets some other way is reported as a conflict, not overwritten. This
service stores the policy, hands it to entitled PCs, and keeps each PC's last report.
- A PC repairing a SAVIO policy someone removed (drift) raises a notification.
- An org without `ai_guard` serves its PCs an empty policy, so turning the add-on off removes
  every setting SAVIO made.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Asset,
    AuditLog,
    Device,
    DeviceBrowserPolicyState,
    GuardUsbWindow,
    NamedBrowserPolicy,
    Notification,
    NotificationCategory,
    NotificationSeverity,
    Organization,
    OrgBrowserPolicy,
    User,
    UserTeam,
    UserTeamMember,
)
from app.models.base import as_utc, utcnow
from app.services.audit import AuditService
from app.services.entitlements import AI_GUARD, features_for
from app.services.notifications import NotificationService

MAX_SITES = 500
# Versions of a policy with exceptions laid over it start here; the org's own count never gets there.
LAYERED_VERSION_FLOOR = 1_000_000_000
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

# D1: sites to block or allow by kind instead of one by one, as a firewall's categories. A host
# covers its subdomains, so these name the personal service, never a shared parent a business also
# uses (outlook.live.com, not live.com; web.whatsapp.com, not whatsapp.com; no Gmail or Drive,
# which D2's Google domains handle). The hosts are copied into the policy when it is saved
# (`category_hosts`, `allowed_category_hosts`), so a PC is only ever served what an admin saved.
# Adult sites and malware or spam are not here on purpose: there are millions and they change
# daily, so no list in code covers them; that needs a filtering DNS service, not this list.
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
    "streaming": ("Entertainment and streaming", (
        "youtube.com", "netflix.com", "primevideo.com", "hotstar.com", "jiocinema.com", "sonyliv.com", "zee5.com",
        "mxplayer.in", "spotify.com", "jiosaavn.com", "gaana.com", "wynk.in", "twitch.tv", "hulu.com",
        "disneyplus.com")),
    "gaming": ("Games", (
        "store.steampowered.com", "steamcommunity.com", "epicgames.com", "roblox.com", "miniclip.com", "poki.com",
        "crazygames.com", "battle.net", "riotgames.com", "ea.com", "y8.com", "friv.com")),
    "gambling": ("Gambling and betting", (
        "bet365.com", "1xbet.com", "betway.com", "parimatch.com", "stake.com", "pokerstars.com", "rummycircle.com",
        "junglee.com", "jungleerummy.com", "pokerbaazi.com", "adda52.com", "my11circle.com", "dream11.com",
        "mpl.live", "winzogames.com")),
    "shopping": ("Shopping", (
        "amazon.in", "amazon.com", "flipkart.com", "myntra.com", "ajio.com", "meesho.com", "nykaa.com",
        "snapdeal.com", "tatacliq.com", "ebay.com", "aliexpress.com", "temu.com", "olx.in")),
    "job_search": ("Job search", (
        "naukri.com", "indeed.com", "foundit.in", "shine.com", "glassdoor.com", "glassdoor.co.in", "timesjobs.com",
        "apna.co", "instahyre.com", "iimjobs.com", "hirist.tech", "cutshort.io")),
    "dating": ("Dating", (
        "tinder.com", "bumble.com", "hinge.co", "okcupid.com", "aisle.co", "trulymadly.com", "happn.com",
        "badoo.com", "quackquack.in")),
    "vpn_proxy": ("VPNs and web proxies", (
        "nordvpn.com", "expressvpn.com", "protonvpn.com", "surfshark.com", "windscribe.com", "tunnelbear.com",
        "hide.me", "hidemyass.com", "proxysite.com", "croxyproxy.com", "kproxy.com", "hidester.com",
        "4everproxy.com", "proxyium.com")),
    "piracy": ("Torrents and piracy", (
        "thepiratebay.org", "1337x.to", "yts.mx", "torrentgalaxy.to", "limetorrents.lol", "nyaa.si",
        "fitgirl-repacks.site", "eztvx.to", "kickasstorrents.to", "torrentz2.nz")),
    "work_tools": ("Work tools", (
        "office.com", "microsoft365.com", "sharepoint.com", "teams.microsoft.com", "docs.google.com",
        "drive.google.com", "meet.google.com", "zoom.us", "slack.com", "notion.so", "atlassian.net",
        "trello.com", "canva.com")),
}
SiteCategory = Literal["file_sharing", "personal_email", "ai_chat", "messaging", "social_media", "paste_sites",
                       "streaming", "gaming", "gambling", "shopping", "job_search", "dating", "vpn_proxy", "piracy",
                       "work_tools"]

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
# A drive's USB storage interface (3b: covers USB 3 drives using UASP), or its disk as approved
# before; the agent translates the old form. Never SCSI\Disk: that is how internal disks look.
_DRIVE_ID = re.compile(r"^(USB\\VID_[0-9A-Fa-f]{4}&PID_[0-9A-Fa-f]{4}|USBSTOR\\[A-Za-z0-9&_.\-]{1,200})\\[A-Za-z0-9&_.\-]{1,100}$")
MAX_APPROVED_DRIVES = 100
MAX_ALLOWED_EXTENSIONS = 50


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


def host_list(v: list[str]) -> list[str]:
    """Host names as typed ("https://Example.com/") made plain and unique, or refused."""
    out: list[str] = []
    for raw in v:
        host = (raw or "").strip().lower().removeprefix("https://").removeprefix("http://").rstrip("/")
        if not _HOST.match(host):
            raise ValueError(f"'{raw[:60]}' is not a host name (like example.com)")
        if host not in out:
            out.append(host)
    return out


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
    # Whole kinds of site always allowed, as `allowed_sites` is: even if a block above covers them.
    allowed_categories: list[SiteCategory] = Field(default_factory=list, max_length=len(SITE_CATEGORIES))
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
    # Security review 3b M2: with a company-accounts rule set, a browser running SAVIO's extension
    # also has private windows and guest mode off and every other extension blocked, except these
    # (Chrome / Edge IDs for those browsers, Firefox IDs for Firefox). Enforced on the PC.
    extension_allowlist: list[str] = Field(default_factory=list, max_length=MAX_ALLOWED_EXTENSIONS)
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

    @field_validator("extension_allowlist")
    @classmethod
    def _allowed_extensions(cls, v: list[str]) -> list[str]:
        out = list(dict.fromkeys(x.strip() for x in v if x.strip()))
        if bad := next((x for x in out if not (_CHROMIUM_ID.match(x) or _FIREFOX_ID.match(x))), None):
            raise ValueError(f"'{bad[:40]}' is not a Chrome, Edge or Firefox extension ID")
        return out

    @field_validator("guard_ignore_kinds", "blocked_categories", "allowed_categories")
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
        return host_list(v)

    @model_validator(mode="after")
    def _extension(self) -> BrowserPolicyBody:
        # The PC gets one block list, and refuses one over its limit.
        if len(set(self.blocked_sites) | set(category_hosts(self.blocked_categories))) > MAX_SITES:
            raise ValueError(f"Blocked sites and categories together come to more than {MAX_SITES} sites")
        if len(set(self.allowed_sites) | set(category_hosts(self.allowed_categories))) > MAX_SITES:
            raise ValueError(f"Allowed sites and categories together come to more than {MAX_SITES} sites")
        if both := set(self.blocked_categories) & set(self.allowed_categories):
            raise ValueError(f"'{SITE_CATEGORIES[min(both)][0]}' cannot be both blocked and allowed")
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


MAX_EXCEPTION_SITES = 100


class ExceptionBody(BaseModel):
    """An exception policy: only the modules it sets change the person's full policy; everything
    else stays as that policy has it. None means "leave it to the full policy"."""
    model_config = ConfigDict(extra="forbid")

    # Browser controls. Extension developer mode is left out: whether it may be on depends on how
    # the full policy installs the extension, which an exception cannot see.
    incognito_off: bool | None = None
    new_profiles_off: bool | None = None
    dev_tools_off: bool | None = None
    block_other_browsers: bool | None = None
    # Websites, added to the full policy's lists. An allowed site is taken off the block list and
    # a blocked one off the allowed list, so the exception always means what it says.
    allow_sites: list[str] = Field(default_factory=list, max_length=MAX_EXCEPTION_SITES)
    block_sites: list[str] = Field(default_factory=list, max_length=MAX_EXCEPTION_SITES)
    allow_categories: list[SiteCategory] = Field(default_factory=list, max_length=len(SITE_CATEGORIES))
    block_categories: list[SiteCategory] = Field(default_factory=list, max_length=len(SITE_CATEGORIES))
    # Google sign-in: [] lets personal Gmail in; domains allow only those accounts.
    google_allowed_domains: list[str] | None = Field(default=None, max_length=MAX_SITES)
    guard_mode: Literal["log", "warn", "justify", "redact", "approve", "block"] | None = None
    usb_mode: UsbMode | None = None
    usb_observe: bool | None = None

    @field_validator("allow_sites", "block_sites")
    @classmethod
    def _sites(cls, v: list[str]) -> list[str]:
        return host_list(v)

    @field_validator("google_allowed_domains")
    @classmethod
    def _google(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else host_list(v)

    @model_validator(mode="after")
    def _something(self) -> ExceptionBody:
        if set(self.allow_sites) & set(self.block_sites) or set(self.allow_categories) & set(self.block_categories):
            raise ValueError("A site or category cannot be both allowed and blocked by one exception")
        if self.usb_mode == "company_drives":
            raise ValueError("Company drives are approved in a full policy; an exception can't list them")
        if not self.model_dump(exclude_defaults=True):
            raise ValueError("An exception must change at least one thing")
        return self


def apply_exception(policy: dict, exc: dict) -> dict:
    """`policy` (a full policy as stored) with the exception's modules laid over it."""
    out = dict(policy)
    for key in ("incognito_off", "new_profiles_off", "dev_tools_off", "block_other_browsers",
                "google_allowed_domains", "guard_mode", "usb_mode", "usb_observe"):
        if exc.get(key) is not None:
            out[key] = exc[key]
    # Categories are read from the list in code here, not copied: an exception's result has a
    # version made from its content, so a changed list is a new version anyway.
    allow = [*(exc.get("allow_sites") or []), *category_hosts(exc.get("allow_categories") or [])]
    block = [*(exc.get("block_sites") or []), *category_hosts(exc.get("block_categories") or [])]
    out["allowed_sites"] = list(dict.fromkeys([*(h for h in out.get("allowed_sites", []) if h not in block), *allow]))
    out["blocked_sites"] = list(dict.fromkeys([*(h for h in out.get("blocked_sites", []) if h not in allow), *block]))
    return out


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


def _check_pilot(org: OrgBrowserPolicy | None, body: BrowserPolicyBody | ExceptionBody) -> None:
    # E8: the first 14 days only record, so the org sees what happens before anyone is
    # interrupted. Enforced here, under the policy page, group policies and suggestions alike.
    # Nothing switches on by itself when the pilot ends: an admin picks the mode.
    if body.guard_mode not in (None, "log") and (until := pilot_until(org)) is not None:
        raise PilotActive(f"AI Guard only records until {as_utc(until):%d %b %Y}, its 14-day pilot. "
                          "End the pilot first to choose another mode.")


def _save(row, org: OrgBrowserPolicy, body: BrowserPolicyBody | ExceptionBody, actor: User) -> list[str]:
    """Write `body` into a policy row (the org's or a group's). A real change takes the org's
    next version number. Returns the fields that changed."""
    new = body.model_dump()
    hosts = category_hosts(getattr(body, "blocked_categories", []))
    allowed = category_hosts(getattr(body, "allowed_categories", []))
    changed = sorted(k for k in new if (row.policy or {}).get(k) != new[k])
    if row.category_hosts != hosts or (row.allowed_category_hosts or []) != allowed:
        changed.append("category_hosts")   # same categories, list updated since: a new version too
    if changed:
        org.seq += 1
        row.policy, row.version, row.updated_by_user_id, row.category_hosts = new, org.seq, actor.id, hosts
        row.allowed_category_hosts = allowed
    return changed


async def put(session: AsyncSession, *, actor: User, body: BrowserPolicyBody) -> OrgBrowserPolicy:
    row = await session.get(OrgBrowserPolicy, actor.org_id)
    _check_pilot(row, body)
    if row is None:
        hosts = category_hosts(body.blocked_categories)
        row = OrgBrowserPolicy(org_id=actor.org_id, policy=body.model_dump(), version=1, seq=1,
                               updated_by_user_id=actor.id, pilot_until=utcnow() + PILOT, category_hosts=hosts,
                               allowed_category_hosts=category_hosts(body.allowed_categories))
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


# ── Named policies for people: user teams and single users ─────────────────────────────────

class NoOrgPolicy(ValueError):
    """Named policies start from, and fall back to, the org's policy: it must exist first."""


class DuplicateName(ValueError):
    """Two policies of one org may not share a name: admins pick them by it."""


class WrongKind(ValueError):
    """A saved policy changes its settings, never its kind."""


class PolicyTargets(BaseModel):
    """Who a named policy is for. Ids only; checked against the org when saved."""
    model_config = ConfigDict(extra="forbid")
    team_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)
    user_ids: list[uuid.UUID] = Field(default_factory=list, max_length=1000)


async def named_policies(session: AsyncSession, org_id) -> list[NamedBrowserPolicy]:
    """The org's named policies, in the order they win: lowest priority, then name."""
    return list((await session.execute(
        select(NamedBrowserPolicy).where(NamedBrowserPolicy.org_id == org_id)
        .order_by(NamedBrowserPolicy.priority, NamedBrowserPolicy.name)
    )).scalars())


async def _check_targets(session: AsyncSession, org_id, targets: PolicyTargets) -> tuple[list[str], list[str]]:
    """The ids as stored (sorted strings), after checking every one belongs to this org."""
    teams, users = set(targets.team_ids), set(targets.user_ids)
    if teams and len((await session.execute(select(UserTeam.id).where(
            UserTeam.org_id == org_id, UserTeam.id.in_(teams)))).all()) != len(teams):
        raise LookupError("No such team.")
    if users and len((await session.execute(select(User.id).where(
            User.org_id == org_id, User.id.in_(users)))).all()) != len(users):
        raise LookupError("No such user.")
    return sorted(map(str, teams)), sorted(map(str, users))


async def put_named(session: AsyncSession, *, actor: User, policy_id, name: str, priority: int,
                    targets: PolicyTargets, body: BrowserPolicyBody | ExceptionBody) -> NamedBrowserPolicy:
    """Create (policy_id None) or change a named policy. A settings change takes the org's next
    version; renaming, re-ranking or reassigning does not: the version names the content."""
    org = await session.get(OrgBrowserPolicy, actor.org_id)
    if org is None:
        raise NoOrgPolicy("Save the default policy first; new policies start from it.")
    _check_pilot(org, body)
    teams, users = await _check_targets(session, actor.org_id, targets)
    same_name = select(NamedBrowserPolicy.id).where(NamedBrowserPolicy.org_id == actor.org_id,
                                                    func.lower(NamedBrowserPolicy.name) == name.lower())
    if policy_id is not None:
        same_name = same_name.where(NamedBrowserPolicy.id != policy_id)
    if (await session.execute(same_name)).first():
        raise DuplicateName(f"A policy named {name!r} already exists.")
    if policy_id is None:
        org.seq += 1
        row = NamedBrowserPolicy(org_id=actor.org_id, name=name, priority=priority, team_ids=teams, user_ids=users,
                                 kind="exception" if isinstance(body, ExceptionBody) else "full",
                                 policy=body.model_dump(), version=org.seq,
                                 category_hosts=category_hosts(getattr(body, "blocked_categories", [])),
                                 allowed_category_hosts=category_hosts(getattr(body, "allowed_categories", [])),
                                 updated_by_user_id=actor.id)
        session.add(row)
        await session.flush()
        changed = ["created"]
    else:
        row = await session.get(NamedBrowserPolicy, policy_id)
        if row is None or row.org_id != actor.org_id:
            raise LookupError("No such policy.")
        if row.kind != ("exception" if isinstance(body, ExceptionBody) else "full"):
            raise WrongKind("A full policy stays full and an exception stays an exception: make a new one.")
        changed = _save(row, org, body, actor)
        for field, value in (("name", name), ("priority", priority), ("team_ids", teams), ("user_ids", users)):
            if getattr(row, field) != value:
                setattr(row, field, value)
                changed.append(field)
    await AuditService(session).record(
        org_id=actor.org_id, actor_id=actor.id, action="guard.named_policy_update",
        target_type="browser_policy", target_id=str(row.id),
        detail={"name": row.name, "changed": changed, "version": row.version, "priority": row.priority,
                "teams": len(teams), "users": len(users)},
    )
    await session.commit()
    return row


async def delete_named(session: AsyncSession, *, actor: User, policy_id) -> None:
    """Its people's PCs go back to the default policy (a different version, so an update)."""
    row = await session.get(NamedBrowserPolicy, policy_id)
    if row is None or row.org_id != actor.org_id:
        raise LookupError("No such policy.")
    await AuditService(session).record(
        org_id=actor.org_id, actor_id=actor.id, action="guard.named_policy_delete",
        target_type="browser_policy", target_id=str(row.id), detail={"name": row.name},
    )
    await session.delete(row)
    await session.commit()


async def assigned_users(session: AsyncSession, org_id, device_ids) -> dict:
    """Device id → the user it is assigned to in Assets, the same link the Tracker reads."""
    if not device_ids:
        return {}
    out: dict = {}
    for did, uid in (await session.execute(
            select(Asset.device_id, Asset.assigned_to_user_id)
            .where(Asset.org_id == org_id, Asset.device_id.in_(list(device_ids)),
                   Asset.assigned_to_user_id.isnot(None)).order_by(Asset.created_at))).all():
        out.setdefault(did, uid)
    return out


async def applies_to(session: AsyncSession, org_id, device_ids) -> dict:
    """Device id → (the full named policy covering it or None for the default, [the exceptions
    covering it, in priority order]), through the user it is assigned to: by name or by one of
    their teams. A PC missing here gets the default policy alone."""
    ranked = await named_policies(session, org_id)
    owners = await assigned_users(session, org_id, device_ids) if ranked else {}
    if not owners:
        return {}
    teams: dict = {}
    for tid, uid in (await session.execute(
            select(UserTeamMember.team_id, UserTeamMember.user_id)
            .where(UserTeamMember.user_id.in_(set(owners.values()))))).all():
        teams.setdefault(uid, set()).add(str(tid))
    out: dict = {}
    for did, uid in owners.items():
        mine = teams.get(uid, set())
        hits = [p for p in ranked if str(uid) in p.user_ids or mine & set(p.team_ids)]
        full = next((p for p in hits if p.kind == "full"), None)
        exceptions = [p for p in hits if p.kind == "exception"]
        if full or exceptions:
            out[did] = (full, exceptions)
    return out


def layered(base, exceptions: list) -> tuple[int, dict]:
    """What a PC applies: `base` (the org's or a full named policy) with `exceptions` laid over it,
    lowest priority number last so it wins, as one block list. The version is the base's when no
    exception applies; otherwise a number made from the result, above any the org issues, so a
    change to any part of it (or a move to another mix) is always a new version on the PC."""
    # D1: the PC gets one block list and one allow list; categories are the portal's way of
    # choosing them. An allowed site wins over a blocked one, as on the PC.
    policy = {k: v for k, v in base.policy.items() if k not in ("blocked_categories", "allowed_categories")}
    policy["allowed_sites"] = list(dict.fromkeys([*policy.get("allowed_sites", []), *(base.allowed_category_hosts or [])]))
    allowed = set(policy["allowed_sites"])
    policy["blocked_sites"] = list(dict.fromkeys(
        [*policy.get("blocked_sites", []), *(h for h in (base.category_hosts or []) if h not in allowed)]))
    for exc in reversed(exceptions):
        policy = apply_exception(policy, exc.policy)
    if not exceptions:
        return base.version, policy
    digest = hashlib.sha256(json.dumps(policy, sort_keys=True, default=str).encode()).hexdigest()
    return LAYERED_VERSION_FLOOR + int(digest[:12], 16) % LAYERED_VERSION_FLOOR, policy


async def for_device(session: AsyncSession, device: Device) -> dict:
    """What a PC should apply: the full named policy of the person it is assigned to (else the
    org's), with that person's exceptions laid over it. Read fresh on every fetch, so giving
    someone another PC moves their policies with them. An org without the add-on gets an empty
    policy at version 0, which tells the agent to remove everything SAVIO set."""
    if not await entitled(session, device.org_id):
        return {"version": 0, "policy": {}}
    row = await session.get(OrgBrowserPolicy, device.org_id)
    if row is None:
        return {"version": 0, "policy": {}}
    full, exceptions = (await applies_to(session, device.org_id, {device.id})).get(device.id, (None, []))
    version, policy = layered(full or row, exceptions)
    return {"version": version, "policy": policy}


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
    for scope, row in [("Everyone", org)] + [(p.name, p) for p in await named_policies(session, org_id)]:
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
