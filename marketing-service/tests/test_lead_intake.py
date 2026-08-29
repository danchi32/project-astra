"""Intake behaviour.

The tests named `test_rejects_*` are the important ones. This endpoint is the only
publicly reachable write in the service, and every one of those cases is a way the lead
database could be written to by someone who is not our website.
"""
import json
import time

import pytest

from app.core.security import sign


def _post(client, secret: str, payload: dict, *, timestamp: str | None = None):
    body = json.dumps(payload, separators=(",", ":")).encode()
    ts = timestamp or str(int(time.time()))
    return client.post(
        "/api/v1/leads/intake",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Astra-Timestamp": ts,
            "X-Astra-Signature": sign(secret, ts, body),
        },
    )


LEAD = {
    "email": "priya@example.com",
    "name": "Priya Nair",
    "company": "Acme Logistics",
    "phone": "+91 98110 00000",
    "source": "contact_form",
    "interest": "Endpoint Automation Assessment",
    "message": "We run about 220 Windows laptops across three sites.",
    "landing_page": "https://technomateai.com/astra/",
    "referrer": "https://www.linkedin.com/",
    "utm_source": "linkedin",
    "utm_medium": "organic-social",
    "utm_campaign": "endpoint-assessment-q3-2026",
    "utm_content": "",
    "utm_term": "",
}


async def test_accepts_a_signed_lead(client, intake_secret):
    response = await _post(client, intake_secret, LEAD)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["is_new_lead"] is True
    assert body["lead_id"] and body["submission_id"]


async def test_stores_attribution_and_derived_fields(client, intake_secret, admin_token):
    created = await _post(client, intake_secret, LEAD)
    lead_id = created.json()["lead_id"]

    response = await client.get(
        f"/api/v1/leads/{lead_id}", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    lead = response.json()

    assert lead["email"] == "priya@example.com"
    assert lead["email_domain"] == "example.com"
    assert lead["is_free_email"] is False
    assert lead["status"] == "new"
    # Scored inline at capture by the rules pass — a lead is never briefly visible without
    # a tier, and this holds with no API key configured (the suite has none).
    assert lead["tier"] == "warm"
    assert lead["score"] > 0
    assert lead["scored_at"] is not None
    assert "work email" in lead["score_reason"]
    # Consent must be recorded at capture — it is the thing that is hardest to add later
    # and the thing a DPDP complaint asks for first.
    assert lead["consent_at"] is not None
    assert lead["consent_source"] == "form:contact_form"

    submission = lead["submissions"][0]
    assert submission["utm_campaign"] == "endpoint-assessment-q3-2026"
    # The website sends "" rather than null for absent UTMs; storing those would fill the
    # campaign index with rows that mean nothing.
    assert submission["utm_content"] is None
    assert submission["utm_term"] is None


async def test_flags_free_email_providers(client, intake_secret, admin_token):
    created = await _post(client, intake_secret, {**LEAD, "email": "astra-test-fixture@gmail.com"})
    lead_id = created.json()["lead_id"]

    response = await client.get(
        f"/api/v1/leads/{lead_id}", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.json()["is_free_email"] is True


async def test_second_submission_reuses_the_lead(client, intake_secret, admin_token):
    first = await _post(client, intake_secret, {**LEAD, "company": None})
    second = await _post(
        client,
        intake_secret,
        {**LEAD, "source": "lead_magnet:offboarding-checklist", "company": "Acme Logistics"},
    )

    assert first.json()["lead_id"] == second.json()["lead_id"]
    assert second.json()["is_new_lead"] is False

    response = await client.get(
        f"/api/v1/leads/{first.json()['lead_id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    lead = response.json()
    assert len(lead["submissions"]) == 2
    # A later submission fills a gap the first one left...
    assert lead["company"] == "Acme Logistics"
    # ...and each touch keeps its own attribution, which is what makes it possible to tell
    # the campaign that found someone from the campaign that converted them.
    assert {s["source"] for s in lead["submissions"]} == {
        "contact_form",
        "lead_magnet:offboarding-checklist",
    }


async def test_email_matching_is_case_insensitive(client, intake_secret):
    first = await _post(client, intake_secret, {**LEAD, "email": "Priya@Example.com"})
    second = await _post(client, intake_secret, {**LEAD, "email": "priya@example.com"})

    assert first.json()["lead_id"] == second.json()["lead_id"]


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"X-Astra-Timestamp": "1"},
        {"X-Astra-Signature": "sha256=deadbeef"},
    ],
    ids=["no-headers", "timestamp-only", "signature-only"],
)
async def test_rejects_requests_without_a_valid_signature(client, headers):
    response = await client.post(
        "/api/v1/leads/intake",
        content=json.dumps(LEAD).encode(),
        headers={"Content-Type": "application/json", **headers},
    )
    assert response.status_code == 401


async def test_rejects_a_forged_signature(client):
    response = await _post(client, "not-the-real-secret", LEAD)
    assert response.status_code == 401


async def test_rejects_a_tampered_body(client, intake_secret):
    """A signature captured from one lead must not validate a different one."""
    body = json.dumps(LEAD, separators=(",", ":")).encode()
    ts = str(int(time.time()))
    signature = sign(intake_secret, ts, body)

    tampered = json.dumps({**LEAD, "email": "attacker@example.com"}, separators=(",", ":"))
    response = await client.post(
        "/api/v1/leads/intake",
        content=tampered.encode(),
        headers={
            "Content-Type": "application/json",
            "X-Astra-Timestamp": ts,
            "X-Astra-Signature": signature,
        },
    )
    assert response.status_code == 401


async def test_rejects_a_replayed_request(client, intake_secret):
    """Yesterday's captured request must not still work today."""
    stale = str(int(time.time()) - 3600)
    response = await _post(client, intake_secret, LEAD, timestamp=stale)
    assert response.status_code == 401


async def test_rejects_an_invalid_email_even_when_signed(client, intake_secret):
    response = await _post(client, intake_secret, {**LEAD, "email": "not-an-email"})
    assert response.status_code == 422


async def test_read_endpoints_require_the_admin_token(client, intake_secret):
    await _post(client, intake_secret, LEAD)

    assert (await client.get("/api/v1/leads")).status_code == 401
    assert (
        await client.get("/api/v1/leads", headers={"Authorization": "Bearer wrong"})
    ).status_code == 401


async def test_admin_can_list_leads(client, intake_secret, admin_token):
    await _post(client, intake_secret, LEAD)

    response = await client.get(
        "/api/v1/leads", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_health_does_not_touch_the_database(client):
    """Cloud Run's probe must survive a Neon cold start."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_rescore_is_available_and_idempotent_without_an_api_key(
    client, intake_secret, admin_token
):
    """With no key configured the model pass is skipped, so rescoring is a no-op.

    That is the property that lets the automation call it unconditionally: it is always
    safe, and never required for a lead to have a usable score.
    """
    created = await _post(client, intake_secret, LEAD)
    lead_id = created.json()["lead_id"]
    auth = {"Authorization": f"Bearer {admin_token}"}

    before = (await client.get(f"/api/v1/leads/{lead_id}", headers=auth)).json()
    rescored = await client.post(f"/api/v1/leads/{lead_id}/rescore", headers=auth)

    assert rescored.status_code == 200
    assert rescored.json()["score"] == before["score"]
    assert rescored.json()["tier"] == before["tier"]


async def test_rescore_requires_the_admin_token(client, intake_secret):
    created = await _post(client, intake_secret, LEAD)
    lead_id = created.json()["lead_id"]

    assert (await client.post(f"/api/v1/leads/{lead_id}/rescore")).status_code == 401


async def test_rescore_on_an_unknown_lead_is_a_404(client, admin_token):
    response = await client.post(
        "/api/v1/leads/00000000-0000-0000-0000-000000000000/rescore",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 404


async def test_a_disqualifying_message_marks_the_lead_disqualified(
    client, intake_secret, admin_token
):
    """Capture never rejects — it records, then labels. The lead is still stored."""
    created = await _post(client, intake_secret, {
        **LEAD,
        "email": "jobseeker@example.com",
        "message": "I am looking for a job at your company, my resume is attached.",
    })
    lead_id = created.json()["lead_id"]

    lead = (await client.get(
        f"/api/v1/leads/{lead_id}", headers={"Authorization": f"Bearer {admin_token}"}
    )).json()

    assert created.status_code == 201          # captured, not refused
    assert lead["status"] == "disqualified"
    assert lead["score"] == 0
    assert "job seeker" in lead["score_reason"]
