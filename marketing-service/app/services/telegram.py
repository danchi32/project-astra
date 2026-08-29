"""Telegram alerts.

Outbound only, for now. The founder gets told about a lead within seconds, with enough
context to reply without opening anything else.

There is deliberately **no webhook and no inline keyboard here**. Buttons mean a public
callback endpoint, and a public callback endpoint that can change state is the sort of
thing that gets designed once, carefully — that happens with the content approval desk,
where it is the whole point. An alert does not need it: the actions a founder takes on a
lead (reply, mark contacted) belong in the mail client and the CRM.

Inert until both `telegram_bot_token` and `telegram_chat_ids` are set.
"""
import asyncio
import html
import logging

import httpx

from app.core.config import get_settings
from app.models.lead import Lead, LeadSubmission, LeadTier

logger = logging.getLogger("astra.mkt.telegram")
settings = get_settings()

_API = "https://api.telegram.org"
#: The visitor is waiting on the request that triggers this. A missed alert is recoverable
#: (the row keeps `notified_at = NULL`); a form that hangs is not.
_TIMEOUT_SECONDS = 3.0
#: Telegram rejects messages over 4096 characters outright, so the quoted lead message is
#: truncated well short of it rather than losing the whole alert.
_MAX_QUOTED_MESSAGE = 1200

_TIER_BADGE = {
    LeadTier.HOT: "🔥 HOT",
    LeadTier.WARM: "🟡 WARM",
    LeadTier.COLD: "⚪ COLD",
    LeadTier.UNSCORED: "• UNSCORED",
}


def _esc(value: str | None) -> str:
    """Escape for Telegram's HTML parse mode.

    Every field below is attacker-controlled — name, company and message come straight
    from a public form. Unescaped, a lead calling themselves `<b>` would at best corrupt
    the alert and at worst make Telegram reject the whole message, so the founder would
    silently stop being told about exactly the leads crafted to avoid it.
    """
    return html.escape(value or "", quote=False)


class TelegramNotifier:
    @property
    def enabled(self) -> bool:
        return bool(settings.telegram_bot_token and self.chat_ids)

    @property
    def chat_ids(self) -> list[str]:
        return [c.strip() for c in settings.telegram_chat_ids.split(",") if c.strip()]

    def compose_lead_alert(self, lead: Lead, submission: LeadSubmission) -> str:
        badge = _TIER_BADGE.get(lead.tier, "• UNSCORED")
        who = _esc(lead.name) or "(no name)"
        company = _esc(lead.company) or "(no company)"

        campaign = " / ".join(
            filter(None, [submission.utm_source, submission.utm_medium, submission.utm_campaign])
        )

        message = (submission.message or "").strip()
        if len(message) > _MAX_QUOTED_MESSAGE:
            message = message[:_MAX_QUOTED_MESSAGE] + "…"

        lines = [
            f"<b>{badge} — new lead ({lead.score}/100)</b>",
            "",
            f"<b>{who}</b> · {company}",
            f"✉️ <code>{_esc(lead.email)}</code>",
        ]
        if lead.phone:
            lines.append(f"📞 <code>{_esc(lead.phone)}</code>")
        lines += [
            "",
            f"<b>Wants:</b> {_esc(submission.interest) or 'not stated'}",
            f"<b>Via:</b> {_esc(submission.source)}"
            + (f" · {_esc(campaign)}" if campaign else ""),
        ]
        if submission.landing_page:
            lines.append(f"<b>Page:</b> {_esc(submission.landing_page)}")
        if message:
            lines += ["", "<blockquote>" + _esc(message) + "</blockquote>"]
        if lead.score_reason:
            lines += ["", f"<i>{_esc(lead.score_reason)}</i>"]

        # The acknowledgement has already gone out with the booking link, so the founder's
        # job is the personal reply — put the mailto one tap away.
        subject = "Re: your enquiry about ASTRA"
        lines += ["", f'<a href="mailto:{_esc(lead.email)}?subject={subject}">Reply now</a>']

        if lead.tier == LeadTier.HOT:
            lines += ["", "⏱ <b>Reply within the hour.</b>"]

        return "\n".join(lines)

    async def send_lead_alert(self, lead: Lead, submission: LeadSubmission) -> bool:
        """Alert every configured chat. True when at least one delivery succeeded."""
        if not self.enabled:
            logger.debug("telegram not configured; skipping alert for lead %s", lead.id)
            return False
        return await self.send(self.compose_lead_alert(lead, submission))

    async def send(self, text: str) -> bool:
        if not self.enabled:
            return False

        url = f"{_API}/bot{settings.telegram_bot_token}/sendMessage"
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            results = await asyncio.gather(
                *(self._send_one(client, url, chat_id, text) for chat_id in self.chat_ids),
                return_exceptions=True,
            )

        delivered = sum(1 for r in results if r is True)
        if delivered == 0:
            logger.warning("telegram alert reached none of %d chats", len(self.chat_ids))
        elif delivered < len(self.chat_ids):
            logger.warning("telegram alert reached %d of %d chats",
                           delivered, len(self.chat_ids))
        return delivered > 0

    async def _send_one(
        self, client: httpx.AsyncClient, url: str, chat_id: str, text: str
    ) -> bool:
        try:
            response = await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                # The alert is the message; a link preview of technomateai.com under every
                # one of them is noise.
                "link_preview_options": {"is_disabled": True},
            })
        except httpx.HTTPError as exc:
            logger.warning("telegram send to %s failed: %s", chat_id, exc)
            return False

        if response.status_code >= 400:
            # Telegram puts the real reason in the body ("chat not found", "bot was
            # blocked"), and without it this is undiagnosable.
            logger.warning("telegram rejected send to %s: %s %s",
                           chat_id, response.status_code, response.text[:200])
            return False
        return True
