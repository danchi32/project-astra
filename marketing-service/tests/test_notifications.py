"""Acknowledgement email and Telegram alert.

No test here makes a network call. The transports are exercised through their composers
and their enabled/disabled gates, because the thing worth pinning is what we *would*
send — an alert that Telegram silently rejects, or an email to someone who opted out, is
a failure nobody notices until leads stop arriving.
"""
import uuid

import pytest

from app.core.config import get_settings
from app.models.base import utcnow
from app.models.lead import Lead, LeadSubmission, LeadTier
from app.services.email import EmailService
from app.services.telegram import TelegramNotifier

settings = get_settings()


def make_lead(**overrides) -> Lead:
    defaults = dict(
        id=uuid.uuid4(), email="priya@example.com", name="Priya Nair",
        company="Acme Logistics", phone="+91 98110 00000",
        email_domain="example.com", is_free_email=False,
        score=82, tier=LeadTier.HOT, score_reason="work email; ~260 endpoints mentioned",
    )
    return Lead(**{**defaults, **overrides})


def make_submission(**overrides) -> LeadSubmission:
    defaults = dict(
        id=uuid.uuid4(), lead_id=uuid.uuid4(), source="contact_form",
        interest="Endpoint Automation Assessment",
        message="We run about 260 Windows laptops across three sites.",
        landing_page="https://technomateai.com/astra/",
        utm_source="linkedin", utm_medium="organic-social",
        utm_campaign="endpoint-assessment-q3-2026",
    )
    return LeadSubmission(**{**defaults, **overrides})


# ── Telegram ───────────────────────────────────────────────────────────────────

def test_notifier_is_inert_without_configuration():
    """The suite configures neither, so this is also the guard against a test emitting."""
    assert TelegramNotifier().enabled is False


def test_chat_ids_are_parsed_as_a_list(monkeypatch):
    monkeypatch.setattr(settings, "telegram_chat_ids", " 123 , 456,, 789 ")
    assert TelegramNotifier().chat_ids == ["123", "456", "789"]


def test_alert_carries_what_a_reply_needs():
    text = TelegramNotifier().compose_lead_alert(make_lead(), make_submission())

    assert "HOT" in text and "82/100" in text
    assert "Priya Nair" in text
    assert "priya@example.com" in text
    assert "+91 98110 00000" in text
    assert "Endpoint Automation Assessment" in text
    assert "260 Windows laptops" in text
    assert "endpoint-assessment-q3-2026" in text
    assert "mailto:priya@example.com" in text
    # The scoring reason travels with the alert, so a wrong tier is visibly wrong.
    assert "~260 endpoints mentioned" in text


def test_hot_leads_carry_the_response_time_reminder():
    hot = TelegramNotifier().compose_lead_alert(make_lead(), make_submission())
    cold = TelegramNotifier().compose_lead_alert(
        make_lead(tier=LeadTier.COLD, score=20), make_submission()
    )

    assert "within the hour" in hot
    assert "within the hour" not in cold


def test_attacker_supplied_fields_are_escaped():
    """Name, company and message all come from a public form.

    Unescaped, a lead calling themselves `<b>` corrupts the alert, and one crafted to
    make Telegram reject the message would silently stop the founder being told about
    exactly the leads designed to avoid notice.
    """
    text = TelegramNotifier().compose_lead_alert(
        make_lead(name="<b>Evil</b>", company="<script>alert(1)</script>"),
        make_submission(message="</blockquote><b>injected</b> & \"quoted\""),
    )

    assert "<b>Evil</b>" not in text
    assert "&lt;b&gt;Evil&lt;/b&gt;" in text
    assert "<script>" not in text
    assert "</blockquote><b>injected</b>" not in text
    assert "&amp;" in text


def test_a_very_long_message_is_truncated():
    """Telegram rejects anything over 4096 characters outright."""
    text = TelegramNotifier().compose_lead_alert(
        make_lead(), make_submission(message="x" * 5000)
    )

    assert len(text) < 4096
    assert "…" in text


def test_a_lead_with_almost_no_detail_still_composes():
    text = TelegramNotifier().compose_lead_alert(
        make_lead(name=None, company=None, phone=None, score_reason=None),
        make_submission(message=None, interest=None, landing_page=None,
                        utm_source=None, utm_medium=None, utm_campaign=None),
    )

    assert "(no name)" in text
    assert "priya@example.com" in text


# ── Acknowledgement email ──────────────────────────────────────────────────────

def test_email_service_is_inert_without_a_transport():
    assert EmailService().enabled is False


def test_acknowledgement_offers_the_booking_link():
    subject, body = EmailService().compose_acknowledgement(make_lead())

    assert "ASTRA" in subject
    assert settings.booking_url in body
    assert "Book a 30-minute assessment" in body


def test_acknowledgement_greets_by_first_name_only():
    """"Hi Priya Nair" reads like a mail merge, which is what this email must not be."""
    _, body = EmailService().compose_acknowledgement(make_lead())
    assert "Hi Priya," in body


def test_acknowledgement_falls_back_to_a_bare_greeting():
    _, body = EmailService().compose_acknowledgement(make_lead(name=None))
    assert "Hi," in body


def test_acknowledgement_escapes_the_name():
    _, body = EmailService().compose_acknowledgement(make_lead(name="<script>x</script>"))
    assert "<script>" not in body


def test_acknowledgement_names_the_legal_entity_and_the_reason_for_the_email():
    """Companies Act disclosure, and the DPDP-facing "why am I getting this"."""
    _, body = EmailService().compose_acknowledgement(make_lead())

    assert "Technomate IT-Solution Private Limited" in body
    assert "because you contacted us" in body


@pytest.mark.asyncio
async def test_no_acknowledgement_is_sent_to_someone_who_opted_out(monkeypatch):
    """Guarded even though the transport is inert here — the gate must precede sending."""
    monkeypatch.setattr(settings, "resend_api_key", "re_test_key")
    service = EmailService()
    assert service.enabled is True

    sent = await service.send_acknowledgement(make_lead(unsubscribed_at=utcnow()))
    assert sent is False
