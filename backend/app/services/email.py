"""Transactional email.

INERT until configured: with no transport set, `enabled` is False and every send
is a safe no-op — so the app works unchanged before email is set up.

Two transports, in priority order:
1. Resend HTTPS API (ASTRA_RESEND_API_KEY) — required on hosts that block SMTP
   (e.g. Railway blocks all outbound SMTP ports).
2. SMTP (ASTRA_SMTP_*) — for local dev or hosts that allow SMTP (e.g. Hostinger).
"""
import re
import smtplib
import ssl
from email.message import EmailMessage

import httpx
from fastapi.concurrency import run_in_threadpool

from app.core.config import get_settings

settings = get_settings()

_RESEND_ENDPOINT = "https://api.resend.com/emails"


def _text_from_html(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).strip()


class EmailService:
    def _smtp_configured(self) -> bool:
        return bool(settings.smtp_host and settings.smtp_user and settings.smtp_password)

    @property
    def enabled(self) -> bool:
        return bool(settings.resend_api_key) or self._smtp_configured()

    @property
    def from_addr(self) -> str:
        return settings.email_from or settings.smtp_user or "onboarding@resend.dev"

    async def send(self, *, to: str, subject: str, html: str, text: str | None = None) -> bool:
        """Send one message. Returns False (no-op) when email isn't configured.
        Prefers the Resend HTTPS API; falls back to SMTP."""
        if settings.resend_api_key:
            return await self._send_resend(to=to, subject=subject, html=html, text=text)
        if self._smtp_configured():
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = self.from_addr
            msg["To"] = to
            msg.set_content(text or _text_from_html(html))
            msg.add_alternative(html, subtype="html")
            await run_in_threadpool(self._deliver, msg)
            return True
        return False

    async def _send_resend(self, *, to: str, subject: str, html: str, text: str | None) -> bool:
        payload: dict = {"from": self.from_addr, "to": [to], "subject": subject, "html": html}
        if text:
            payload["text"] = text
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                _RESEND_ENDPOINT,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json=payload,
            )
        resp.raise_for_status()
        return True

    def _deliver(self, msg: EmailMessage) -> None:  # blocking; runs in a threadpool
        with self._smtp() as server:
            server.send_message(msg)

    def _smtp(self):
        """Open an authenticated SMTP session (implicit SSL on 465, else STARTTLS)."""
        host, port = settings.smtp_host, settings.smtp_port
        context = ssl.create_default_context()
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, context=context, timeout=20)
        else:
            server = smtplib.SMTP(host, port, timeout=20)
            server.starttls(context=context)
        server.login(settings.smtp_user, settings.smtp_password)
        return server

    def verify_connection(self) -> tuple[bool, str]:
        """Validate the active transport (no email sent) and report the real error.
        Used by the /health/email-check diagnostic. Never raises."""
        if settings.resend_api_key:
            try:
                with httpx.Client(timeout=15) as client:
                    r = client.get(
                        "https://api.resend.com/domains",
                        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                    )
                if r.status_code == 200:
                    return True, "Resend API key valid"
                return False, f"Resend API returned {r.status_code}: {r.text[:200]}"
            except Exception as exc:
                return False, f"{type(exc).__name__}: {exc}"
        if not self._smtp_configured():
            return False, "email not configured"
        try:
            with self._smtp() as server:
                server.noop()
            return True, "connected and authenticated OK (SMTP)"
        except Exception as exc:  # surface the real SMTP error (not secret)
            return False, f"{type(exc).__name__}: {exc}"

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

    async def send_password_reset(self, *, to: str, name: str, link: str) -> bool:
        ttl = settings.password_reset_ttl_minutes
        html = _shell(
            "Reset your password",
            f"""<p>Hi {name},</p>
            <p>We received a request to reset your ASTRA password. Click below to choose a new one:</p>
            <p style="margin:24px 0"><a href="{link}" style="display:inline-block;background:#2563eb;color:#fff;
            text-decoration:none;padding:10px 18px;border-radius:8px;font-weight:600">Reset password</a></p>
            <p style="color:#666">This link expires in {ttl} minutes. If you didn't request it, you can safely
            ignore this email — your password won't change.</p>""",
        )
        return await self.send(
            to=to, subject="Reset your ASTRA password", html=html,
            text=f"Reset your ASTRA password: {link} (expires in {ttl} minutes). If you didn't request this, ignore this email.",
        )

    async def send_password_changed(self, *, to: str, name: str) -> bool:
        html = _shell(
            "Your password was changed",
            f"""<p>Hi {name},</p>
            <p>Your ASTRA password was just changed. If this was you, no action is needed.</p>
            <p style="color:#666">If you didn't do this, contact your administrator immediately.</p>""",
        )
        return await self.send(
            to=to, subject="Your ASTRA password was changed", html=html,
            text="Your ASTRA password was just changed. If this wasn't you, contact your administrator immediately.",
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
