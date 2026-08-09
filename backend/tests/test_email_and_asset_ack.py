"""Per-org email sending (DNS-verified) + asset assignment acknowledgement."""
import uuid

import pytest
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
        subject_tmpl=None, body_tmpl=None,
        context={"employee_name": "Sam", "asset_name": "Dell 7440", "org_name": "Acme"},
        ack_link="https://x/ack?token=t")
    assert "Dell 7440" in subj
    assert "Sam" in html and "Acme" in html
    assert "Acknowledge receipt" in html
    assert "https://x/ack?token=t" in html and "https://x/ack?token=t" in text


def test_render_custom_template_positions_button_once():
    subj, html, _ = render_asset_assignment(
        subject_tmpl="Your {{asset_name}} is ready",
        body_tmpl="Hi {{employee_name}}\n{{acknowledge_button}}\nThanks, {{org_name}}",
        context={"asset_name": "Laptop", "employee_name": "Sam", "org_name": "Acme"},
        ack_link="https://x/a")
    assert subj == "Your Laptop is ready"
    assert html.count("Acknowledge receipt") == 1  # not appended twice


def test_render_escapes_injected_values():
    _, html, _ = render_asset_assignment(
        subject_tmpl=None, body_tmpl="{{asset_name}}",
        context={"asset_name": "<script>bad</script>"}, ack_link="https://x/a")
    assert "<script>bad" not in html
    assert "&lt;script&gt;" in html


def test_render_device_placeholders():
    _, html, _ = render_asset_assignment(
        subject_tmpl="Kit for {{employee_name}}",
        body_tmpl="Host {{hostname}} · CPU {{cpu}} · RAM {{ram}} · Serial {{serial}} · "
                  "Storage {{storage}} · Apps {{software}} · Logged in {{device_user}} · {{status}}",
        context={
            "employee_name": "Sam", "hostname": "PC-1", "cpu": "Intel i7", "ram": "16 GB",
            "serial": "SN-9", "storage": "512 GB", "software": "142 apps",
            "device_user": "ACME\\sam", "status": "in use",
        },
        ack_link="https://x/a")
    for token in ("PC-1", "Intel i7", "16 GB", "SN-9", "512 GB", "142 apps", "in use"):
        assert token in html


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

    async def fake_send(self, *, to, subject, html, text=None, from_name=None,
                        from_email=None, reply_to=None, cc=None):
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


# ── Two ways to send, and the reply that used to disappear ─────────────────


async def test_a_new_org_can_send_before_touching_dns(session_factory, admin_user):
    """The point of offering the shared sender. Publishing DNS records is a request to
    another team in most companies; an org should not be unable to send while it waits."""
    from app.services.email_integration import EmailIntegrationService

    async with session_factory() as session:
        sender = await EmailIntegrationService.resolve_sender(
            session, admin_user.org_id, org_name="Acme Corp"
        )
    assert sender.shared is True
    assert sender.from_address is None, "None means 'use ASTRA's own configured address'"
    assert sender.from_name == "Acme Corp (via ASTRA)", (
        "said out loud — a recipient who checks the address will see it is ours anyway"
    )


async def test_choosing_the_shared_sender_records_a_reply_to(session_factory, admin_user):
    """Without one, an employee replying to an asset email writes to ASTRA, where nobody
    reads a customer's staff mail. The question vanishes with no bounce and no trace."""
    from app.models import EmailSendMethod
    from app.services.email_integration import EmailIntegrationService

    async with session_factory() as session:
        await EmailIntegrationService(session).choose_sender(
            actor=admin_user, method=EmailSendMethod.SHARED,
            from_name="Acme IT", reply_to="helpdesk@acme.com",
        )

    async with session_factory() as session:
        sender = await EmailIntegrationService.resolve_sender(
            session, admin_user.org_id, org_name="Acme Corp"
        )
    assert sender.shared is True
    assert sender.from_name == "Acme IT (via ASTRA)"
    assert sender.reply_to == "helpdesk@acme.com"


async def test_the_reply_to_reaches_the_actual_send(session_factory, admin_user, monkeypatch):
    """The header has to survive the whole path, not just be stored. This is the message
    most likely to be replied to — someone confused about a laptop they were just handed."""
    from app.models import Asset, AssetCategory, EmailSendMethod
    from app.services.assets import AssetService
    from app.services.email import EmailService
    from app.services.email_integration import EmailIntegrationService

    captured: dict = {}

    async def fake_send_assignment(self, **kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(EmailService, "send_asset_assignment", fake_send_assignment)
    monkeypatch.setattr(EmailService, "enabled", property(lambda self: True))

    async with session_factory() as session:
        await EmailIntegrationService(session).choose_sender(
            actor=admin_user, method=EmailSendMethod.SHARED,
            from_name="Acme IT", reply_to="helpdesk@acme.com",
        )
        asset = Asset(
            org_id=admin_user.org_id, name="Dell Latitude", category=AssetCategory.LAPTOP,
            assigned_to_user_id=admin_user.id, ack_token="tok-reply-to",
        )
        session.add(asset)
        await session.flush()
        await AssetService(session)._send_ack_email(asset)

    assert captured.get("reply_to") == "helpdesk@acme.com"
    assert captured.get("from_email") is None, "shared sender uses ASTRA's own address"


async def test_registering_your_own_domain_selects_it(session_factory, admin_user, monkeypatch):
    """Setting up a sending domain IS choosing it. Without this an admin could finish DNS
    verification and still have everything go out from ASTRA's address, which looks exactly
    like the feature being broken with nothing anywhere explaining it."""
    from app.models import EmailSendMethod
    from app.services import email_domains
    from app.services.email_integration import EmailIntegrationService

    async def fake_create(domain):
        return {"id": "dom_1", "status": "pending", "records": []}

    monkeypatch.setattr(email_domains, "create_domain", fake_create)
    monkeypatch.setattr(email_domains, "normalize_records", lambda p: [])

    async with session_factory() as session:
        row = await EmailIntegrationService(session).configure(
            actor=admin_user, from_name="Acme IT", from_address="it@acme.com"
        )
    assert row.method is EmailSendMethod.DNS


# ── The shared sender is a paid thing, decided by the operator ─────────────


@pytest.fixture
async def set_plan(session_factory, admin_user):
    """Change the org's plan for one test, and put it back afterwards.

    A test that permanently rewrites shared fixture state is a landmine for whatever runs
    next — and the failure lands somewhere unrelated, hours later, on a line nobody
    touched. The teardown is the point of this being a fixture rather than a helper.
    """
    from app.models import Organization

    async with session_factory() as s:
        org = await s.get(Organization, admin_user.org_id)
        original = (org.plan, org.entitlement_overrides)

    async def _set(plan, overrides=None):
        async with session_factory() as s:
            org = await s.get(Organization, admin_user.org_id)
            org.plan = plan
            org.entitlement_overrides = overrides
            await s.commit()

    yield _set

    async with session_factory() as s:
        org = await s.get(Organization, admin_user.org_id)
        org.plan, org.entitlement_overrides = original
        await s.commit()


async def test_an_essential_org_cannot_pick_the_shared_sender(session_factory, admin_user, set_plan):
    """Sending from ASTRA's address is gated for reputation: on the shared sender every
    organization draws on one sending domain, so one bad recipient list degrades delivery
    for everyone else on it."""
    from app.models import EmailSendMethod
    from app.services.email_integration import EmailIntegrationService, SharedSenderNotEntitled

    await set_plan("essential")
    async with session_factory() as session:
        with pytest.raises(SharedSenderNotEntitled):
            await EmailIntegrationService(session).choose_sender(
                actor=admin_user, method=EmailSendMethod.SHARED,
                from_name="Acme IT", reply_to="helpdesk@acme.com",
            )


async def test_the_operator_can_grant_it_to_one_organization(session_factory, admin_user, set_plan):
    """The exception path. Same override map, same org page, same audit trail as every
    other feature — an operator should not need a new mechanism to say yes once."""
    from app.models import EmailSendMethod
    from app.services.email_integration import EmailIntegrationService

    await set_plan("essential",
                    {"shared_email_sender": True})
    async with session_factory() as session:
        row = await EmailIntegrationService(session).choose_sender(
            actor=admin_user, method=EmailSendMethod.SHARED,
            from_name="Acme IT", reply_to="helpdesk@acme.com",
        )
    assert row.method is EmailSendMethod.SHARED


async def test_the_operator_can_take_it_away_from_a_paid_plan(session_factory, admin_user, set_plan):
    """Overrides work in both directions — a Professional customer who abuses the shared
    domain can be moved off it without changing what they pay for."""
    from app.models import EmailSendMethod
    from app.services.email_integration import EmailIntegrationService, SharedSenderNotEntitled

    await set_plan("professional",
                    {"shared_email_sender": False})
    async with session_factory() as session:
        with pytest.raises(SharedSenderNotEntitled):
            await EmailIntegrationService(session).choose_sender(
                actor=admin_user, method=EmailSendMethod.SHARED, from_name="x", reply_to=None,
            )


async def test_losing_the_entitlement_does_not_stop_mail_already_going_out(
    session_factory, admin_user, set_plan
):
    """Deliberate. Cutting a customer's employee-facing email the moment a plan changes
    turns a billing event into a support incident — the asset acknowledgements simply stop
    with nobody told. The portal surfaces it instead, and the operator has the override if
    a hard cut is genuinely wanted."""
    from app.models import EmailSendMethod
    from app.services.email_integration import EmailIntegrationService

    await set_plan("professional")
    async with session_factory() as session:
        await EmailIntegrationService(session).choose_sender(
            actor=admin_user, method=EmailSendMethod.SHARED,
            from_name="Acme IT", reply_to="helpdesk@acme.com",
        )

    await set_plan("essential")
    async with session_factory() as session:
        sender = await EmailIntegrationService.resolve_sender(
            session, admin_user.org_id, org_name="Acme Corp"
        )
        allowed = await EmailIntegrationService.shared_sender_allowed(
            session, admin_user.org_id
        )
    assert sender.shared is True, "mail keeps flowing"
    assert allowed is False, "but the portal is told, so it can say so"


async def test_choosing_your_own_domain_never_needs_an_entitlement(session_factory, admin_user, set_plan):
    """The free path has to stay free, or an Essential customer has no way to send at all."""
    from app.models import EmailSendMethod
    from app.services.email_integration import EmailIntegrationService

    await set_plan("essential")
    async with session_factory() as session:
        row = await EmailIntegrationService(session).choose_sender(
            actor=admin_user, method=EmailSendMethod.DNS, from_name="Acme IT", reply_to=None,
        )
    assert row.method is EmailSendMethod.DNS


# ── Copying IT on the acknowledgement ──────────────────────────────────────


async def test_the_cc_list_reaches_the_send(session_factory, admin_user, monkeypatch):
    """A CC and not a BCC, which is the entire request: a hidden copy is invisible to the
    recipient's mail client, so their Reply All would go to the sender alone and IT would
    still never see the answer."""
    from app.models import Asset, AssetCategory
    from app.services.assets import AssetService
    from app.services.email import EmailService
    from app.services.email_integration import EmailIntegrationService

    captured: dict = {}

    async def fake_send_assignment(self, **kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(EmailService, "send_asset_assignment", fake_send_assignment)
    monkeypatch.setattr(EmailService, "enabled", property(lambda self: True))

    async with session_factory() as session:
        await EmailIntegrationService(session).update_asset_template(
            actor=admin_user, subject="", body="",
            cc=["it@acme.com", "assets@acme.com"],
        )
        asset = Asset(
            org_id=admin_user.org_id, name="Dell Latitude", category=AssetCategory.LAPTOP,
            assigned_to_user_id=admin_user.id, ack_token="tok-cc",
        )
        session.add(asset)
        await session.flush()
        await AssetService(session)._send_ack_email(asset)

    assert captured.get("cc") == ["it@acme.com", "assets@acme.com"]


async def test_a_cc_of_the_recipient_is_dropped(session_factory, monkeypatch):
    """Copying someone on their own mail is noise, not a copy — and it is an easy thing for
    an admin to type when the assignee is a member of the IT team."""
    from app.services.email import EmailService

    sent: dict = {}

    async def fake_resend(self, **kwargs):
        sent.update(kwargs)
        return True

    monkeypatch.setattr(EmailService, "_send_resend", fake_resend)
    monkeypatch.setattr("app.services.email.settings.resend_api_key", "re_test", raising=False)

    await EmailService().send(
        to="priya@acme.com", subject="s", html="<p>h</p>",
        cc=["PRIYA@acme.com", "it@acme.com"],
    )
    assert sent["cc"] == ["it@acme.com"], "case-insensitive, and the duplicate is gone"


@pytest.mark.parametrize("given,expected", [
    (["it@acme.com", "IT@ACME.COM"], ["it@acme.com"]),          # deduped, lowercased
    (["it@acme.com", "not an email", ""], ["it@acme.com"]),      # junk dropped, rest kept
    ([], None),                                                  # empty means none
    ([f"a{i}@acme.com" for i in range(9)],                       # capped
     [f"a{i}@acme.com" for i in range(5)]),
])
def test_the_cc_list_is_cleaned_rather_than_rejected(given, expected):
    """A trailing comma in a pasted list should not fail the whole save and take the
    admin's template edits down with it."""
    from app.services.email_integration import _clean_cc

    assert _clean_cc(given) == expected


async def test_clearing_the_cc_actually_clears_it(session_factory, admin_user):
    """An empty list is a real instruction. If it were treated the same as "not supplied",
    the last address could never be removed."""
    from app.services.email_integration import EmailIntegrationService

    async with session_factory() as session:
        await EmailIntegrationService(session).update_asset_template(
            actor=admin_user, subject="", body="", cc=["it@acme.com"],
        )
    async with session_factory() as session:
        row = await EmailIntegrationService(session).update_asset_template(
            actor=admin_user, subject="", body="", cc=[],
        )
    assert row.asset_email_cc is None


async def test_a_password_reset_is_never_copied_to_anyone(session_factory, admin_user, monkeypatch):
    """The scope line. These messages are written for one person, and copying an
    administrator on them would hand that person's account to somebody else."""
    from app.services.email import EmailService
    from app.services.email_integration import EmailIntegrationService

    sent: dict = {}

    async def fake_resend(self, **kwargs):
        sent.update(kwargs)
        return True

    monkeypatch.setattr(EmailService, "_send_resend", fake_resend)
    monkeypatch.setattr("app.services.email.settings.resend_api_key", "re_test", raising=False)

    async with session_factory() as session:
        await EmailIntegrationService(session).update_asset_template(
            actor=admin_user, subject="", body="", cc=["it@acme.com"],
        )

    await EmailService().send_password_reset(to="priya@acme.com", name="Priya", link="https://x/y")
    assert sent.get("cc") is None
