"""Zoho Bigin sync.

The CRM is where a lead becomes a sales conversation, so this pushes two records: a
Contact (the person) and a Pipeline record (the opportunity). It never pulls — Bigin is
downstream of this service, not a second source of truth for lead data. A human editing a
company name in Bigin should not have it silently overwritten by the next form fill, and a
human moving a deal forward is the authority on where it is.

Names in here were **read from the live org**, not guessed, and two of them would have been
wrong:

* The records module is `Pipelines`. `/Deals` 404s, even though `settings/fields?module=Deals`
  works — a legacy alias on the metadata endpoint only.
* A Pipeline record has three mandatory fields, not one: `Deal_Name`, `Stage`, and
  `Sub_Pipeline`. Omitting `Sub_Pipeline` fails the create.

Inert until `bigin_refresh_token` is set.
"""
import asyncio
import logging
import time

import httpx

from app.core.config import get_settings
from app.models.lead import Lead, LeadStatus, LeadSubmission, LeadTier

logger = logging.getLogger("astra.mkt.bigin")
settings = get_settings()

_TIMEOUT_SECONDS = 10.0

#: Bigin's records module for opportunities. Not "Deals" — see the module docstring.
_PIPELINES_MODULE = "Pipelines"

#: The stage names configured in this org, matching the pipeline in docs/GO_TO_MARKET.md.
#: If someone renames a stage in Bigin without changing this map, creates fail loudly with
#: INVALID_DATA rather than landing a deal in the wrong column — which is the failure we
#: want, and why `verify_stages()` exists.
STAGE_FOR_STATUS: dict[LeadStatus, str] = {
    LeadStatus.NEW: "New",
    LeadStatus.CONTACTED: "Contacted",
    LeadStatus.QUALIFIED: "Qualified",
    LeadStatus.DISCOVERY_BOOKED: "Discovery Booked",
    LeadStatus.PILOT_PROPOSED: "Pilot Proposed",
    LeadStatus.PILOT_ACTIVE: "Pilot Active",
    LeadStatus.CLOSED_WON: "Closed Won",
    LeadStatus.CLOSED_LOST: "Closed Lost",
    # No separate stage: a disqualified lead is a lost one, and the reason already
    # travels in the description. An extra stage would clutter every board view to
    # record something nobody works.
    LeadStatus.DISQUALIFIED: "Closed Lost",
}


class BiginError(Exception):
    """Bigin refused the request. Carries its message, which is usually specific."""


class BiginClient:
    """Thin client with a cached access token.

    Zoho access tokens last an hour and the refresh endpoint is rate limited, so the token
    is held in memory and refreshed only when it is close to expiring. On Cloud Run each
    instance keeps its own — which is fine, and much simpler than sharing one.
    """

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        return bool(
            settings.bigin_refresh_token
            and settings.bigin_client_id
            and settings.bigin_client_secret
        )

    async def _token(self) -> str:
        # Refresh 60s early: a token that expires between this check and the API call
        # would surface as a confusing 401 on an otherwise valid request.
        async with self._lock:
            if self._access_token and time.time() < self._expires_at - 60:
                return self._access_token

            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    f"{settings.bigin_accounts_domain}/oauth/v2/token",
                    data={
                        "grant_type": "refresh_token",
                        "client_id": settings.bigin_client_id,
                        "client_secret": settings.bigin_client_secret,
                        "refresh_token": settings.bigin_refresh_token,
                    },
                )
            payload = response.json()
            if "access_token" not in payload:
                # Zoho returns 200 with an error body, so status alone proves nothing.
                raise BiginError(f"token refresh failed: {payload}")

            self._access_token = payload["access_token"]
            self._expires_at = time.time() + int(payload.get("expires_in", 3600))
            return self._access_token

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        token = await self._token()
        async with httpx.AsyncClient(
            base_url=f"{settings.bigin_api_domain}/bigin/v2",
            headers={"Authorization": f"Zoho-oauthtoken {token}"},
            timeout=_TIMEOUT_SECONDS,
        ) as client:
            response = await client.request(method, path, **kwargs)

        if response.status_code == 204:
            return {}
        try:
            payload = response.json()
        except ValueError as exc:
            raise BiginError(f"{response.status_code}: {response.text[:200]}") from exc

        if response.status_code >= 400:
            raise BiginError(f"{response.status_code}: {payload}")
        return payload

    # ── Discovery ──────────────────────────────────────────────────────────────

    async def stage_names(self) -> list[str]:
        """The stage picklist as Bigin currently has it."""
        payload = await self._request("GET", "/settings/fields", params={"module": "Deals"})
        for field in payload.get("fields", []):
            if field.get("api_name") == "Stage":
                return [v.get("display_value") for v in field.get("pick_list_values", [])]
        return []

    async def sub_pipeline_names(self) -> list[str]:
        payload = await self._request("GET", "/settings/fields", params={"module": "Deals"})
        for field in payload.get("fields", []):
            if field.get("api_name") == "Sub_Pipeline":
                return [
                    v.get("display_value") for v in field.get("pick_list_values", [])
                    if v.get("display_value") != "-None-"
                ]
        return []

    async def verify_stages(self) -> list[str]:
        """Which stages this code expects but the org does not have.

        Worth calling at deploy time. A renamed stage otherwise shows up as a create
        failing for one lead at a time, weeks later, in a log nobody is reading.
        """
        actual = set(await self.stage_names())
        return sorted({s for s in STAGE_FOR_STATUS.values() if s not in actual})

    # ── Writes ─────────────────────────────────────────────────────────────────

    async def upsert_contact(self, lead: Lead) -> str:
        """Create or update the Contact, keyed on email. Returns its Bigin id.

        `upsert` rather than `create` so a re-run — a retry, a replayed submission, a
        manual resync — does not litter the CRM with duplicates of the same person.
        """
        # Last_Name is the only mandatory Contact field. A lead who gave no name still
        # has to land somewhere findable, so the email stands in for it.
        last_name = (lead.name or "").strip() or lead.email
        first_name = ""
        if lead.name and " " in lead.name.strip():
            first_name, _, last_name = lead.name.strip().partition(" ")

        record = {
            "Last_Name": last_name[:80],
            "Email": lead.email,
            "Description": lead.score_reason or "",
        }
        if first_name:
            record["First_Name"] = first_name[:40]
        if lead.phone:
            record["Phone"] = lead.phone[:30]
        if lead.company:
            record["Account_Name"] = {"name": lead.company[:100]}

        payload = await self._request(
            "POST", "/Contacts/upsert",
            json={"data": [record], "duplicate_check_fields": ["Email"]},
        )
        return self._first_id(payload, "contact")

    async def create_pipeline_record(
        self, lead: Lead, submission: LeadSubmission | None, contact_id: str,
        *, sub_pipeline: str,
    ) -> str:
        """Create the opportunity. Three mandatory fields, all supplied."""
        company = lead.company or lead.email_domain or lead.email
        record = {
            "Deal_Name": f"{company} — {(submission.interest if submission else None) or 'Enquiry'}"[:120],
            "Stage": STAGE_FOR_STATUS.get(lead.status, "New"),
            "Sub_Pipeline": sub_pipeline,
            "Contact_Name": {"id": contact_id},
            "Description": self._describe(lead, submission),
        }

        payload = await self._request(
            "POST", f"/{_PIPELINES_MODULE}", json={"data": [record]}
        )
        return self._first_id(payload, "pipeline record")

    async def update_stage(self, record_id: str, status: LeadStatus) -> None:
        await self._request(
            "PUT", f"/{_PIPELINES_MODULE}",
            json={"data": [{"id": record_id, "Stage": STAGE_FOR_STATUS.get(status, "New")}]},
        )

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _first_id(payload: dict, what: str) -> str:
        rows = payload.get("data") or []
        if not rows:
            raise BiginError(f"no {what} returned: {payload}")
        row = rows[0]
        if row.get("code") not in ("SUCCESS", None):
            raise BiginError(f"{what} rejected: {row.get('code')} {row.get('message')}")
        record_id = (row.get("details") or {}).get("id")
        if not record_id:
            raise BiginError(f"{what} returned no id: {row}")
        return str(record_id)

    @staticmethod
    def _describe(lead: Lead, submission: LeadSubmission | None) -> str:
        """The context a salesperson wants before replying, in one field.

        Bigin has no natural home for attribution, and a deal without it cannot be traced
        back to the content that produced it — which is the measurement the whole system
        exists to close.
        """
        badge = {LeadTier.HOT: "HOT", LeadTier.WARM: "WARM"}.get(lead.tier, "COLD")
        lines = [f"[{badge} {lead.score}/100] {lead.score_reason or ''}".strip()]
        if submission:
            campaign = " / ".join(filter(None, [
                submission.utm_source, submission.utm_medium, submission.utm_campaign,
            ]))
            lines += [
                "",
                f"Source: {submission.source}" + (f" · {campaign}" if campaign else ""),
                f"Landing page: {submission.landing_page or '—'}",
                "",
                (submission.message or "").strip() or "(no message)",
            ]
        return "\n".join(lines)[:32000]
