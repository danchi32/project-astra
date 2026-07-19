"""Per-org email sending (DNS-verified) + asset assignment acknowledgement."""
import uuid

from sqlalchemy import select

from app.models import Asset
from app.services import email_domains
from app.services.email import EmailService


async def _assign(client, headers, user_id, name="Dell Latitude 7440"):
    return await client.post("/api/v1/assets", json={
        "name": name, "category": "laptop", "assigned_to_user_id": str(user_id),
    }, headers=headers)


async def _token_for(session_factory, asset_id: str) -> str | None:
    async with session_factory() as s:
        asset = (await s.execute(
            select(Asset).where(Asset.id == uuid.UUID(asset_id))
        )).scalar_one()
        return asset.ack_token


# ── Asset acknowledgement (no email provider required) ──────────────────────

async def test_assigning_asset_marks_pending(client, admin_headers, regular_user):
    created = await _assign(client, admin_headers, regular_user.id)
    assert created.status_code == 201, created.text
    assert created.json()["acknowledgement_status"] == "pending"


async def test_acknowledge_via_emailed_token(client, admin_headers, regular_user, session_factory):
    created = await _assign(client, admin_headers, regular_user.id)
    asset_id = created.json()["id"]
    token = await _token_for(session_factory, asset_id)
    assert token

    page = await client.get(f"/api/v1/assets/acknowledge?token={token}")
    assert page.status_code == 200
    assert "confirmed" in page.text.lower()

    got = (await client.get(f"/api/v1/assets/{asset_id}", headers=admin_headers)).json()
    assert got["acknowledgement_status"] == "acknowledged"
    assert got["acknowledged_at"] is not None


async def test_acknowledge_unknown_token_is_graceful(client):
    page = await client.get("/api/v1/assets/acknowledge?token=does-not-exist")
    assert page.status_code == 200
    assert "not recognized" in page.text.lower()


async def test_unassigning_clears_acknowledgement(client, admin_headers, regular_user, session_factory):
    created = await _assign(client, admin_headers, regular_user.id)
    asset_id = created.json()["id"]
    resp = await client.patch(
        f"/api/v1/assets/{asset_id}", json={"assigned_to_user_id": None}, headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.json()["acknowledgement_status"] == "not_required"
    assert await _token_for(session_factory, asset_id) is None


async def test_resend_requires_an_assignee(client, admin_headers):
    created = await client.post("/api/v1/assets", json={"name": "Spare monitor", "category": "monitor"},
                                headers=admin_headers)
    asset_id = created.json()["id"]
    resp = await client.post(f"/api/v1/assets/{asset_id}/resend-acknowledgement", headers=admin_headers)
    assert resp.status_code == 409


# ── Email settings: DNS-verified sending domain (Resend mocked) ─────────────

def _fake_domain(status="pending", name="acme.com"):
    return {
        "id": "dom_123", "status": status, "records": [
            {"record": "DKIM", "type": "TXT", "name": f"resend._domainkey.{name}",
             "value": "p=MIGf...", "ttl": "Auto"},
            {"record": "SPF", "type": "TXT", "name": f"send.{name}",
             "value": "v=spf1 include:amazonses.com ~all", "ttl": "Auto"},
        ],
    }


async def test_configure_and_verify_sending_domain(client, admin_headers, monkeypatch):
    async def fake_create(name):
        return _fake_domain(name=name)
    monkeypatch.setattr(email_domains, "create_domain", fake_create)

    resp = await client.post("/api/v1/settings/email", json={
        "from_name": "Acme IT", "from_address": "it-support@acme.com",
    }, headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "pending"
    assert body["domain"] == "acme.com"
    assert body["from_address"] == "it-support@acme.com"
    assert len(body["dns_records"]) == 2
    assert {r["purpose"] for r in body["dns_records"]} == {"DKIM", "SPF"}

    # Verify: provider now reports the domain verified.
    async def fake_verify(domain_id):
        return {}
    async def fake_get(domain_id):
        return _fake_domain(status="verified")
    monkeypatch.setattr(email_domains, "verify_domain", fake_verify)
    monkeypatch.setattr(email_domains, "get_domain", fake_get)

    v = await client.post("/api/v1/settings/email/verify", headers=admin_headers)
    assert v.status_code == 200, v.text
    assert v.json()["status"] == "verified"
    assert v.json()["verified_at"] is not None


async def test_email_settings_admin_only(client, user_headers):
    assert (await client.get("/api/v1/settings/email", headers=user_headers)).status_code == 403
    assert (await client.post("/api/v1/settings/email", json={
        "from_name": "X", "from_address": "x@x.com"}, headers=user_headers)).status_code == 403


async def test_ack_email_sends_as_verified_org_address(
    client, admin_headers, regular_user, monkeypatch
):
    # Configure + verify a sending domain.
    async def fake_create(name):
        return _fake_domain(name=name)
    async def fake_verify(domain_id):
        return {}
    async def fake_get(domain_id):
        return _fake_domain(status="verified")
    monkeypatch.setattr(email_domains, "create_domain", fake_create)
    monkeypatch.setattr(email_domains, "verify_domain", fake_verify)
    monkeypatch.setattr(email_domains, "get_domain", fake_get)
    await client.post("/api/v1/settings/email", json={
        "from_name": "Acme IT", "from_address": "it-support@acme.com"}, headers=admin_headers)
    await client.post("/api/v1/settings/email/verify", headers=admin_headers)

    # Capture the send; force email "enabled" so the send path runs in tests.
    captured: dict = {}

    async def fake_send_assignment(self, **kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(EmailService, "enabled", property(lambda self: True))
    monkeypatch.setattr(EmailService, "send_asset_assignment", fake_send_assignment)

    created = await _assign(client, admin_headers, regular_user.id)
    assert created.status_code == 201, created.text
    # The email goes to the assignee, FROM the org's verified address.
    assert captured.get("to") == regular_user.email
    assert captured.get("from_email") == "it-support@acme.com"
    assert "acknowledge" in captured.get("ack_link", "").lower()
