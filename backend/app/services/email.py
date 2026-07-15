"""Transactional email over SMTP.

INERT until configured: with no SMTP host/user/password set, `enabled` is False
and every send is a safe no-op that returns False — so registration and the rest
of the app work unchanged before (and without) email being set up.

Works with Hostinger SMTP (smtp.hostinger.com:465 SSL, or :587 STARTTLS) or any
SMTP provider — only the env vars change.
"""
import re
import smtplib
import ssl
from email.message import EmailMessage

from fastapi.concurrency import run_in_threadpool

from app.core.config import get_settings

settings = get_settings()


def _text_from_html(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).strip()


class EmailService:
    @property
    def enabled(self) -> bool:
        return bool(settings.smtp_host and settings.smtp_user and settings.smtp_password)

    @property
    def from_addr(self) -> str:
        return settings.email_from or settings.smtp_user or "noreply@astra.local"

    async def send(self, *, to: str, subject: str, html: str, text: str | None = None) -> bool:
        """Send one message. Returns False (no-op) when email isn't configured."""
        if not self.enabled:
            return False
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.from_addr
        msg["To"] = to
        msg.set_content(text or _text_from_html(html))
        msg.add_alternative(html, subtype="html")
        await run_in_threadpool(self._deliver, msg)
        return True

    def _deliver(self, msg: EmailMessage) -> None:  # blocking; runs in a threadpool
        host, port = settings.smtp_host, settings.smtp_port
        context = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as server:
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as server:
                server.starttls(context=context)
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)

    # -- templated messages ----------------------------------------------------

    async def send_otp(self, *, to: str, code: str) -> bool:
        ttl = settings.otp_ttl_minutes
        html = _shell(
            "Confirm your email",
            f"""<p>Use this code to finish creating your ASTRA organization:</p>
            <p style="font-size:32px;font-weight:700;letter-spacing:6px;margin:24px 0;color:#111">{code}</p>
            <p style="color:#666">This code expires in {ttl} minutes. If you didn't request it, you can ignore this email.</p>""",
        )
        return await self.send(
            to=to, subject=f"Your ASTRA verification code: {code}", html=html,
            text=f"Your ASTRA verification code is {code}. It expires in {ttl} minutes.",
        )

    async def send_welcome(self, *, to: str, name: str, org_name: str, trial_days: int) -> bool:
        app_url = (settings.public_app_url or "").rstrip("/")
        button = (
            f'<a href="{app_url}" style="display:inline-block;background:#2563eb;color:#fff;'
            f'text-decoration:none;padding:10px 18px;border-radius:8px;font-weight:600">Open ASTRA</a>'
            if app_url else ""
        )
        html = _shell(
            "Welcome to ASTRA",
            f"""<p>Hi {name},</p>
            <p>Your organization <strong>{org_name}</strong> is set up and your
            <strong>{trial_days}-day free trial</strong> has started.</p>
            <p>To get going: install the Windows agent from <em>Devices → Get installer</em>,
            then invite your team under <em>Users</em>.</p>
            <p style="margin:24px 0">{button}</p>
            <p style="color:#666">Welcome aboard — the ASTRA team.</p>""",
        )
        return await self.send(
            to=to, subject="Welcome to ASTRA", html=html,
            text=f"Hi {name}, your organization {org_name} is set up and your {trial_days}-day trial has started. Open ASTRA at {app_url}",
        )


def _shell(title: str, body_html: str) -> str:
    return f"""<div style="font-family:Segoe UI,Arial,sans-serif;max-width:520px;margin:0 auto;padding:24px;color:#111">
      <div style="font-size:22px;font-weight:700;color:#2563eb;margin-bottom:8px">⬡ ASTRA</div>
      <h1 style="font-size:18px;margin:0 0 16px">{title}</h1>
      {body_html}
    </div>"""
