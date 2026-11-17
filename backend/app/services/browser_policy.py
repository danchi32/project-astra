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
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Device,
    DeviceBrowserPolicyState,
    NotificationCategory,
    NotificationSeverity,
    Organization,
    OrgBrowserPolicy,
    User,
)
from app.models.base import utcnow
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
_FIREFOX_ID = re.compile(r"^(\{[0-9a-fA-F-]{36}\}|[A-Za-z0-9._-]{1,80}@[A-Za-z0-9.-]{1,80})$")


class BrowserPolicyBody(BaseModel):
    """The same rules the agent's `BrowserPolicy.Validate` applies, checked here first, so a
    policy the agent would refuse is never saved."""
    incognito_off: bool = False
    extension_developer_mode_off: bool = False
    dev_tools_off: bool = False
    new_profiles_off: bool = False
    blocked_sites: list[str] = Field(default_factory=list, max_length=MAX_SITES)
    allowed_sites: list[str] = Field(default_factory=list, max_length=MAX_SITES)
    google_allowed_domains: list[str] = Field(default_factory=list, max_length=MAX_SITES)
    chrome_extension_id: str | None = None
    edge_extension_id: str | None = None
    firefox_extension_id: str | None = None
    firefox_extension_url: str | None = Field(default=None, max_length=500)
    # D3: the extension's own settings, handed to it as managed policy where it is forced in.
    guard_mode: Literal["log", "warn", "justify", "redact", "approve", "block"] = "log"
    guard_watched_sites: list[str] = Field(default_factory=list, max_length=MAX_SITES)
    guard_ignore_kinds: list[FindingKind] = Field(default_factory=lambda: ["Email"], max_length=len(FINDING_KINDS))
    guard_keywords: list[str] = Field(default_factory=list, max_length=MAX_KEYWORDS)

    @field_validator("guard_ignore_kinds")
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
        for name, rx in (("chrome_extension_id", _CHROMIUM_ID), ("edge_extension_id", _CHROMIUM_ID),
                         ("firefox_extension_id", _FIREFOX_ID)):
            value = getattr(self, name)
            if value is not None and not rx.match(value):
                raise ValueError(f"{name} is malformed")
        if (self.firefox_extension_id is None) != (self.firefox_extension_url is None):
            raise ValueError("A Firefox extension needs both an ID and an install URL")
        if self.firefox_extension_url and not self.firefox_extension_url.startswith("https://"):
            raise ValueError("The Firefox extension URL must be https")
        return self


class BrowserResult(BaseModel):
    browser: Literal["Chrome", "Edge", "Firefox"]
    set: list[str] = Field(default_factory=list, max_length=50)
    repaired: list[str] = Field(default_factory=list, max_length=50)
    removed: list[str] = Field(default_factory=list, max_length=50)
    conflicts: list[str] = Field(default_factory=list, max_length=50)
    error: str | None = Field(default=None, max_length=500)

    @field_validator("set", "repaired", "removed", "conflicts")
    @classmethod
    def _names(cls, v: list[str]) -> list[str]:
        return [n[:100] for n in v]


class BrowserPolicyReport(BaseModel):
    version: int = Field(ge=0)
    results: list[BrowserResult] = Field(max_length=10)


async def entitled(session: AsyncSession, org_id) -> bool:
    org = await session.get(Organization, org_id)
    return org is not None and AI_GUARD in features_for(org.plan, org.entitlement_overrides)


async def get(session: AsyncSession, org_id) -> OrgBrowserPolicy | None:
    return await session.get(OrgBrowserPolicy, org_id)


async def put(session: AsyncSession, *, actor: User, body: BrowserPolicyBody) -> OrgBrowserPolicy:
    row = await session.get(OrgBrowserPolicy, actor.org_id)
    new = body.model_dump()
    before = row.policy if row else {}
    changed = sorted(k for k in new if before.get(k) != new[k])
    if row is None:
        row = OrgBrowserPolicy(org_id=actor.org_id, policy=new, version=1, updated_by_user_id=actor.id)
        session.add(row)
    elif changed:
        row.policy, row.version, row.updated_by_user_id = new, row.version + 1, actor.id
    await AuditService(session).record(
        org_id=actor.org_id, actor_id=actor.id, action="guard.browser_policy_update",
        target_type="organization", target_id=str(actor.org_id),
        detail={"changed": changed, "version": row.version},
    )
    await session.commit()
    return row


async def for_device(session: AsyncSession, device: Device) -> dict:
    """What a PC should apply. An org without the add-on gets an empty policy at version 0,
    which tells the agent to remove everything SAVIO set."""
    if not await entitled(session, device.org_id):
        return {"version": 0, "policy": {}}
    row = await session.get(OrgBrowserPolicy, device.org_id)
    return {"version": row.version, "policy": row.policy} if row else {"version": 0, "policy": {}}


async def record_report(session: AsyncSession, device: Device, report: BrowserPolicyReport) -> None:
    results = [r.model_dump() for r in report.results]
    state = await session.get(DeviceBrowserPolicyState, device.id)
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
        await NotificationService(session).notify(
            org_id=device.org_id, category=NotificationCategory.SYSTEM,
            severity=NotificationSeverity.WARNING, title="Browser policy tampered",
            message=f"{device.hostname}: {', '.join(repaired[:5])} had been changed and was put back.",
            link="/guard",
        )
    await session.commit()


async def device_states(session: AsyncSession, org_id) -> list[tuple[DeviceBrowserPolicyState, str]]:
    return list((await session.execute(
        select(DeviceBrowserPolicyState, Device.hostname)
        .join(Device, Device.id == DeviceBrowserPolicyState.device_id)
        .where(DeviceBrowserPolicyState.org_id == org_id)
        .order_by(Device.hostname)
    )).all())
