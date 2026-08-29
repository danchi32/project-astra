"""The acknowledgement email.

One message, sent within seconds of a form submission, carrying the booking link. It is
the highest-leverage thing this whole service does: the go-to-market plan promises a reply
inside one business hour, and a promise bounded by when someone next opens an inbox is not
one that can be kept at 9pm on a Saturday.

It does not pretend to be a human. It says the enquiry arrived, offers the calendar, and
tells them a person will follow up — because a prospect who books from this email has
converted without anyone touching it, and one who waits has still been answered.

Two transports, same priority order as the product backend: Resend's HTTPS API first
(works on hosts that block outbound SMTP), then SMTP. Inert with neither configured.
"""
import html
import logging
import re
import smtplib
import ssl
from email.message import EmailMessage

import httpx
from fastapi.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.models.lead import Lead

logger = logging.getLogger("astra.mkt.email")
settings = get_settings()

_RESEND_ENDPOINT = "https://api.resend.com/emails"
#: The visitor is waiting. Short enough not to hold the form, long enough for a normal
#: API round trip.
_TIMEOUT_SECONDS = 4.0


def _text_from_html(body: str) -> str:
    return re.sub(r"<[^>]+>", "", body).strip()


class EmailService:
    @property
    def enabled(self) -> bool:
        return bool(settings.resend_api_key or self._smtp_configured())

    @staticmethod
    def _smtp_configured() -> bool:
        return bool(settings.smtp_host and settings.smtp_user and settings.smtp_password)

    def compose_acknowledgement(self, lead: Lead) -> tuple[str, str]:
        """Subject and HTML body.

        Addressed by first name only when we have one — "Hi Priya Nair" reads like a
        mail merge, which is precisely the impression this email exists to avoid.
        """
        first_name = (lead.name or "").strip().split(" ")[0]
        greeting = f"Hi {html.escape(first_name)}," if first_name else "Hi,"

        subject = "Thanks for getting in touch — ASTRA"
        body = f"""\
<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
            font-size:15px;line-height:1.6;color:#1b1526;max-width:560px">
  <p>{greeting}</p>

  <p>Thanks for reaching out about ASTRA. Your enquiry has landed with us and someone
     from the team will reply personally — usually within a business hour.</p>

  <p>If it is easier, you can put a time straight in the calendar and skip the back and
     forth:</p>

  <p>
    <a href="{html.escape(settings.booking_url)}"
       style="display:inline-block;background:#9a2fbb;color:#ffffff;text-decoration:none;
              padding:11px 20px;border-radius:4px;font-weight:600">
      Book a 30-minute assessment
    </a>
  </p>

  <p style="color:#6a6280;font-size:14px">
     It is a working session, not a pitch: we look at how your Windows fleet is supported
     today and where repetitive work can safely be reduced.
  </p>

  <p style="margin-top:28px">Best regards,<br>
     The ASTRA team<br>
     <a href="{html.escape(settings.site_url)}"
        style="color:#9a2fbb">{html.escape(settings.site_url)}</a>
  </p>

  <p style="color:#8b8598;font-size:12px;margin-top:28px;border-top:1px solid #e6e1ee;
            padding-top:14px">
     Technomate IT-Solution Private Limited · Ayodhya Ganj, Dadri, Gautam Budh Nagar,
     Uttar Pradesh 203207, India<br>
     You are receiving this because you contacted us through
     {html.escape(settings.site_url)}.
  </p>
</div>"""
        return subject, body

    async def send_acknowledgement(self, lead: Lead) -> bool:
        """Send it. Never raises — a failed acknowledgement must not fail the form."""
        if not self.enabled:
            logger.debug("email not configured; no acknowledgement for lead %s", lead.id)
            return False
        if lead.unsubscribed_at is not None:
            # They asked not to be emailed. A transactional-looking reply to a form they
            # just filled is defensible; sending it to someone who has opted out is not.
            logger.info("lead %s has unsubscribed; skipping acknowledgement", lead.id)
            return False

        subject, body = self.compose_acknowledgement(lead)
        try:
            if settings.resend_api_key:
                return await self._send_resend(lead.email, subject, body)
            return await run_in_threadpool(self._send_smtp, lead.email, subject, body)
        except Exception as exc:  # noqa: BLE001 — deliberately total
            logger.warning("acknowledgement to lead %s failed: %s", lead.id, exc)
            return False

    async def _send_resend(self, to: str, subject: str, body: str) -> bool:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(
                _RESEND_ENDPOINT,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": settings.email_from,
                    "to": [to],
                    "subject": subject,
                    "html": body,
                    "text": _text_from_html(body),
                },
            )
        if response.status_code >= 400:
            logger.warning("resend rejected the acknowledgement: %s %s",
                           response.status_code, response.text[:200])
            return False
        return True

    def _send_smtp(self, to: str, subject: str, body: str) -> bool:
        message = EmailMessage()
        message["From"] = settings.email_from
        message["To"] = to
        message["Subject"] = subject
        message.set_content(_text_from_html(body))
        message.add_alternative(body, subtype="html")

        context = ssl.create_default_context()
        # Port 465 is implicit SSL; anything else means STARTTLS. Same rule as the
        # product backend and the website's PHP mailer.
        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port,
                                  context=context, timeout=_TIMEOUT_SECONDS) as server:
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(message)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port,
                              timeout=_TIMEOUT_SECONDS) as server:
                server.starttls(context=context)
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(message)
        return True
