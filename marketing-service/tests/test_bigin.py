"""Bigin sync.

Offline: no test here reaches Zoho. What is pinned is the mapping and the record shapes,
because the two facts that would have been wrong are structural — the module is
`Pipelines`, not `Deals`, and a Pipeline record has three mandatory fields, not one. Both
were read from the live org; these tests stop them drifting back to a guess.
"""
import uuid

import pytest

from app.models.lead import Lead, LeadStatus, LeadSubmission, LeadTier
from app.services.bigin import STAGE_FOR_STATUS, BiginClient, BiginError


def make_lead(**overrides) -> Lead:
    defaults = dict(
        id=uuid.uuid4(), email="priya@example.com", name="Priya Nair",
        company="Acme Logistics", phone="+91 98110 00000",
        email_domain="example.com", is_free_email=False,
        score=82, tier=LeadTier.HOT, status=LeadStatus.NEW,
        score_reason="work email; ~260 endpoints mentioned",
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


def test_client_is_inert_without_credentials():
    assert BiginClient().enabled is False


# ── Stage mapping ──────────────────────────────────────────────────────────────

def test_every_lead_status_maps_to_a_stage():
    """A status with no stage would fail at create time, on one lead, in production."""
    unmapped = [s for s in LeadStatus if s not in STAGE_FOR_STATUS]
    assert unmapped == []


def test_pipeline_statuses_map_to_the_gtm_stage_names():
    assert STAGE_FOR_STATUS[LeadStatus.NEW] == "New"
    assert STAGE_FOR_STATUS[LeadStatus.DISCOVERY_BOOKED] == "Discovery Booked"
    assert STAGE_FOR_STATUS[LeadStatus.PILOT_ACTIVE] == "Pilot Active"


def test_disqualified_is_closed_lost_rather_than_its_own_stage():
    """The reason already travels in the description; a ninth stage nobody works would
    only clutter every board view."""
    assert STAGE_FOR_STATUS[LeadStatus.DISQUALIFIED] == "Closed Lost"
    assert STAGE_FOR_STATUS[LeadStatus.CLOSED_LOST] == "Closed Lost"


# ── The description a salesperson reads ────────────────────────────────────────

def test_description_carries_tier_score_and_attribution():
    """Bigin has no native home for attribution, and without it a won deal cannot be
    traced back to the content that produced it — the measurement the system exists for."""
    text = BiginClient._describe(make_lead(), make_submission())

    assert "[HOT 82/100]" in text
    assert "~260 endpoints mentioned" in text
    assert "linkedin / organic-social / endpoint-assessment-q3-2026" in text
    assert "https://technomateai.com/astra/" in text
    assert "260 Windows laptops" in text


def test_description_handles_a_lead_with_no_submission():
    text = BiginClient._describe(make_lead(tier=LeadTier.COLD, score=12), None)
    assert "[COLD 12/100]" in text


def test_description_says_so_when_there_is_no_message():
    text = BiginClient._describe(make_lead(), make_submission(message=None))
    assert "(no message)" in text


# ── Response parsing ───────────────────────────────────────────────────────────

def test_first_id_returns_the_created_record_id():
    payload = {"data": [{"code": "SUCCESS", "details": {"id": "554023000000123001"}}]}
    assert BiginClient._first_id(payload, "contact") == "554023000000123001"


@pytest.mark.parametrize(
    ("payload", "because"),
    [
        ({"data": []}, "empty data array"),
        ({}, "no data key at all"),
        ({"data": [{"code": "INVALID_DATA", "message": "invalid value for Stage"}]},
         "a per-record rejection"),
        ({"data": [{"code": "SUCCESS", "details": {}}]}, "success without an id"),
    ],
)
def test_first_id_raises_on_anything_it_cannot_trust(payload: dict, because: str):
    """Zoho reports per-record failures inside a 200 response.

    Reading the id optimistically would store None as `crm_record_id` and make every later
    sync think the deal already exists — so the lead would never reach the CRM and nothing
    would ever say so.
    """
    with pytest.raises(BiginError):
        BiginClient._first_id(payload, "pipeline record")


def test_rejection_message_is_preserved():
    """"INVALID_DATA: Stage" is a five-second fix; "sync failed" is an afternoon."""
    payload = {"data": [{"code": "INVALID_DATA", "message": "invalid value for Stage"}]}

    with pytest.raises(BiginError, match="INVALID_DATA"):
        BiginClient._first_id(payload, "pipeline record")
