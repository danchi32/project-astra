"""Telegram alerts.

Outbound only, for now. The founder gets told about a lead within seconds, with enough
context to reply without opening anything else.

Lead alerts have no buttons, and that is still deliberate: the actions a founder takes on
a lead (reply, mark contacted) belong in the mail client and the CRM, and a button that
changes state needs a public callback endpoint. That endpoint now exists for the content
approval desk, where it is the whole point — see `app/services/approval_desk.py` and
`app/api/v1/telegram.py`. What lives here is only the transport it speaks over.

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
#: The approval desk is not on anyone's critical path — no visitor is watching a spinner —
#: and Telegram's own API is occasionally slow to edit a message. It gets room the lead
#: alert cannot have.
_DESK_TIMEOUT_SECONDS = 15.0
#: Telegram truncates any message over this. A draft plus its metadata can exceed it, so
#: the desk trims the body rather than letting Telegram reject the whole review.
MAX_MESSAGE = 4096

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


#: Public alias. The approval desk renders attacker-controlled text too — a draft can
#: quote a prospect's own words — and it should not have to reach for a private name to
#: escape it correctly.
escape_html = _esc


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


    # ── Transport for the approval desk ────────────────────────────────────────
    # Three thin wrappers. They return message ids and booleans rather than raising,
    # because every caller is inside a webhook handler that must answer 200 quickly:
    # Telegram redelivers an update it did not get an answer for, and an exception
    # escaping here would turn one failed edit into a redelivery loop.

    async def send_message(
        self, chat_id: str, text: str, keyboard: dict | None = None
    ) -> int | None:
        """Send one message to one chat. Returns Telegram's message id, or None."""
        if not settings.telegram_bot_token:
            return None

        payload: dict = {
            "chat_id": chat_id,
            "text": text[:MAX_MESSAGE],
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        }
        if keyboard is not None:
            payload["reply_markup"] = keyboard

        data = await self._call("sendMessage", payload)
        return (data or {}).get("message_id")

    async def edit_message(
        self, chat_id: str, message_id: int, text: str, keyboard: dict | None = None
    ) -> bool:
        """Rewrite a message in place.

        The desk edits rather than replies, so a decided draft stops looking undecided.
        Passing no keyboard removes the buttons, which is how a handled review stops
        offering an action that would now be refused.
        """
        payload: dict = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text[:MAX_MESSAGE],
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
            "reply_markup": keyboard if keyboard is not None else {"inline_keyboard": []},
        }
        return await self._call("editMessageText", payload) is not None

    async def answer_callback(self, callback_query_id: str, text: str = "") -> bool:
        """Stop the button spinning.

        Telegram spins a tapped button for a few seconds and then shows a client-side
        error unless this is called. Skipping it makes every successful approval look
        broken to the person who made it.
        """
        return await self._call("answerCallbackQuery", {
            "callback_query_id": callback_query_id,
            "text": text[:200],
        }) is not None

    async def _call(self, method: str, payload: dict) -> dict | None:
        if not settings.telegram_bot_token:
            return None

        url = f"{_API}/bot{settings.telegram_bot_token}/{method}"
        try:
            async with httpx.AsyncClient(timeout=_DESK_TIMEOUT_SECONDS) as client:
                response = await client.post(url, json=payload)
        except httpx.HTTPError as exc:
            logger.warning("telegram %s failed: %s", method, exc)
            return None

        if response.status_code >= 400:
            logger.warning("telegram rejected %s: %s %s",
                           method, response.status_code, response.text[:300])
            return None
        try:
            return response.json().get("result") or {}
        except ValueError:
            logger.warning("telegram %s returned a non-JSON body", method)
            return None
