"""Hand a captured lead to the downstream automation (n8n).

Best-effort by construction. The lead is already committed before anything in this module
runs, so every failure here degrades the experience without losing the record: the
submission keeps `dispatched_at = NULL`, and the sweeper in `list_undispatched` finds it.

The webhook is signed with the same scheme the website uses to call us, so n8n can verify
that a lead notification really came from this service rather than from anyone who
guessed the URL.
"""
import json
import logging
import time

import httpx

from app.core.config import get_settings
from app.core.security import sign
from app.models.lead import Lead, LeadSubmission

logger = logging.getLogger("astra.mkt.dispatch")
settings = get_settings()

#: Short. The visitor is waiting on the HTTP response that triggered this, and a lead that
#: is stored but undispatched is a far better outcome than a form that appears to hang.
_TIMEOUT_SECONDS = 5.0


class LeadDispatcher:
    @property
    def enabled(self) -> bool:
        return bool(settings.n8n_lead_webhook_url)

    def payload_for(self, lead: Lead, submission: LeadSubmission) -> dict:
        """Everything n8n needs to score, notify and sync, without a callback.

        Deliberately denormalised. n8n reading this does not need to query us back for the
        lead's details, which keeps the workflow simple and means a credential rotation on
        this service does not break the workflow mid-run.
        """
        return {
            "lead_id": str(lead.id),
            "submission_id": str(submission.id),
            "email": lead.email,
            "name": lead.name,
            "company": lead.company,
            "phone": lead.phone,
            "email_domain": lead.email_domain,
            "is_free_email": lead.is_free_email,
            "is_new_lead": len(lead.submissions) <= 1 if lead.submissions else True,
            "status": lead.status.value,
            "tier": lead.tier.value,
            "score": lead.score,
            "submission": {
                "source": submission.source,
                "interest": submission.interest,
                "message": submission.message,
                "landing_page": submission.landing_page,
                "referrer": submission.referrer,
                "utm_source": submission.utm_source,
                "utm_medium": submission.utm_medium,
                "utm_campaign": submission.utm_campaign,
                "utm_content": submission.utm_content,
                "utm_term": submission.utm_term,
                "created_at": submission.created_at.isoformat(),
            },
        }

    async def dispatch(self, lead: Lead, submission: LeadSubmission) -> bool:
        """POST the lead to n8n. Returns whether it was accepted.

        Never raises. A caller in the request path must not be able to fail because a
        downstream automation is unreachable.
        """
        if not self.enabled:
            logger.debug("n8n webhook not configured; skipping dispatch")
            return False

        body = json.dumps(self.payload_for(lead, submission), separators=(",", ":")).encode()
        timestamp = str(int(time.time()))
        headers = {"Content-Type": "application/json", "X-Astra-Timestamp": timestamp}
        if settings.n8n_webhook_secret:
            headers["X-Astra-Signature"] = sign(settings.n8n_webhook_secret, timestamp, body)

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    settings.n8n_lead_webhook_url, content=body, headers=headers
                )
            if response.status_code >= 400:
                logger.warning(
                    "n8n rejected lead %s with %s: %s",
                    lead.id, response.status_code, response.text[:300],
                )
                return False
            return True
        except httpx.HTTPError as exc:
            # Warning, not error: this is an expected and fully recoverable condition. The
            # sweeper will retry, and an alert should fire on the backlog, not on one miss.
            logger.warning("n8n dispatch failed for lead %s: %s", lead.id, exc)
            return False
