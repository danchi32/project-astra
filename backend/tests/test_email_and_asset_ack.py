"""Per-org email sending (DNS-verified) + asset assignment acknowledgement."""
import uuid

from sqlalchemy import select

from app.models import Asset
from app.services import email_domains
from app.services.email import EmailService
from app.services.email_templates import render_asset_assignment


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


# ── Asset-assignment email template ────────────────────────────────────────

def test_render_default_template_has_link_and_values():
    subj, html, text = render_asset_assignment(
        subject_tmpl=None, body_tmpl=None, employee_name="Sam", asset_name="Dell 7440",
        asset_tag="A-1", org_name="Acme", ack_link="https://x/ack?token=t")
    assert "Dell 7440" in subj
    assert "Sam" in html and "Acme" in html
    assert "Acknowledge receipt" in html
    assert "https://x/ack?token=t" in html and "https://x/ack?token=t" in text


def test_render_custom_template_positions_button_once():
    subj, html, _ = render_asset_assignment(
        subject_tmpl="Your {{asset_name}} is ready",
        body_tmpl="Hi {{employee_name}}\n{{acknowledge_button}}\nThanks, {{org_name}}",
        employee_name="Sam", asset_name="Laptop", asset_tag=None,
        org_name="Acme", ack_link="https://x/a")
    assert subj == "Your Laptop is ready"
    assert html.count("Acknowledge receipt") == 1  # not appended twice


def test_render_escapes_injected_values():
    _, html, _ = render_asset_assignment(
        subject_tmpl=None, body_tmpl="{{asset_name}}", employee_name="x",
        asset_name="<script>bad</script>", asset_tag=None, org_name="o", ack_link="https://x/a")
    assert "<script>bad" not in html
    assert "&lt;script&gt;" in html


async def test_get_settings_returns_default_template(client, admin_headers):
    body = (await client.get("/api/v1/settings/email", headers=admin_headers)).json()
    assert body["asset_email_subject"]
    assert body["asset_email_body"]
    assert "employee_name" in body["asset_email_placeholders"]


async def test_customize_and_persist_template(client, admin_headers):
    resp = await client.put("/api/v1/settings/email/asset-template", json={
        "subject": "Kit for {{employee_name}}",
        "body": "Hi {{employee_name}}, your {{asset_name}} is ready.",
    }, headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["asset_email_subject"] == "Kit for {{employee_name}}"
    again = (await client.get("/api/v1/settings/email", headers=admin_headers)).json()
    assert again["asset_email_body"].startswith("Hi {{employee_name}}")


async def test_custom_template_used_on_assignment(client, admin_headers, regular_user, monkeypatch):
    await client.put("/api/v1/settings/email/asset-template", json={
        "subject": "CUSTOMSUBJ {{asset_name}}", "body": "CUSTOMBODY {{employee_name}}",
    }, headers=admin_headers)
    captured: dict = {}

    async def fake_send(self, *, to, subject, html, text=None, from_name=None, from_email=None):
        captured.update(to=to, subject=subject, html=html)
        return True

    monkeypatch.setattr(EmailService, "enabled", property(lambda self: True))
    monkeypatch.setattr(EmailService, "send", fake_send)
    await _assign(client, admin_headers, regular_user.id)
    assert captured["subject"].startswith("CUSTOMSUBJ")
    assert "CUSTOMBODY" in captured["html"]


async def test_asset_template_is_admin_only(client, user_headers):
    resp = await client.put("/api/v1/settings/email/asset-template",
                            json={"subject": "x", "body": "y"}, headers=user_headers)
    assert resp.status_code == 403


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
