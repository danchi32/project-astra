"""Connecting an organization to the helpdesk it already runs.

The credential is the point. It can read every ticket, contact and asset in a customer's
service desk, so most of what is pinned here is that it goes in and never comes back out —
not through the API, not through the audit log, not through a mask.
"""
import pytest

from app.core import crypto
from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _secrets_key(monkeypatch):
    monkeypatch.setattr(get_settings(), "secrets_key", crypto.generate_key(), raising=False)


# ── Configuring ────────────────────────────────────────────────────────────


async def test_it_starts_unconfigured_and_not_ready(client, admin_headers):
    body = (await client.get("/api/v1/settings/helpdesk", headers=admin_headers)).json()
    assert body["enabled"] is False
    assert body["ready"] is False
    assert body["api_key_masked"] == ""


async def test_saving_a_connection_makes_it_ready(client, admin_headers):
    resp = await client.patch("/api/v1/settings/helpdesk", headers=admin_headers, json={
        "domain": "acme", "api_key": "fs-secret-key-9911", "enabled": True,
        "default_priority": 2, "workspace_id": 1,
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ready"] is True
    assert body["domain"] == "acme"
    assert body["default_priority"] == 2
    assert body["workspace_id"] == 1


@pytest.mark.parametrize("given", [
    "acme",
    "acme.freshservice.com",
    "https://acme.freshservice.com",
    "https://acme.freshservice.com/a/tickets/12",
    "  ACME.freshservice.com  ",
])
async def test_whatever_the_admin_pastes_resolves_to_one_instance(client, admin_headers,
                                                                  given):
    """They will paste from their address bar. Rejecting four of these five would be a
    support ticket about the ticketing integration."""
    resp = await client.patch("/api/v1/settings/helpdesk", headers=admin_headers,
                              json={"domain": given})
    assert resp.json()["domain"] == "acme"


async def test_a_partial_update_keeps_the_rest(client, admin_headers):
    """Set up over more than one sitting. An omitted field must not blank what is there —
    especially the credential, which would silently disconnect the integration."""
    await client.patch("/api/v1/settings/helpdesk", headers=admin_headers,
                       json={"domain": "acme", "api_key": "fs-secret-key-9911",
                             "enabled": True})
    await client.patch("/api/v1/settings/helpdesk", headers=admin_headers,
                       json={"default_priority": 3})
    body = (await client.get("/api/v1/settings/helpdesk", headers=admin_headers)).json()
    assert body["domain"] == "acme"
    assert body["default_priority"] == 3
    assert body["ready"] is True, "omitting api_key must not clear it"


async def test_the_action_map_survives_the_round_trip(client, admin_headers):
    """This is what puts a ticket in front of the team that handles that kind of problem."""
    mapping = {"restart_outlook": {"category": "Software", "sub_category": "Office 365"}}
    await client.patch("/api/v1/settings/helpdesk", headers=admin_headers,
                       json={"category_map": mapping})
    body = (await client.get("/api/v1/settings/helpdesk", headers=admin_headers)).json()
    assert body["category_map"] == mapping


# ── The credential never comes back ────────────────────────────────────────


async def test_the_api_key_is_never_returned(client, admin_headers):
    secret = "fs-secret-key-9911"
    saved = (await client.patch("/api/v1/settings/helpdesk", headers=admin_headers,
                                json={"domain": "acme", "api_key": secret})).json()
    fetched = (await client.get("/api/v1/settings/helpdesk", headers=admin_headers)).json()

    for body in (saved, fetched):
        assert secret not in str(body)
        assert "api_key" not in body
    # Enough to recognise which key is saved, never enough to use it.
    assert fetched["api_key_masked"].endswith("9911")


async def test_the_audit_log_records_the_change_but_not_the_secret(client, admin_headers):
    secret = "fs-secret-key-9911"
    await client.patch("/api/v1/settings/helpdesk", headers=admin_headers,
                       json={"domain": "acme", "api_key": secret})
    logs = (await client.get("/api/v1/audit-logs", headers=admin_headers)).json()
    entries = [e for e in logs["items"] if e["action"] == "helpdesk.settings.update"]
    assert entries, "a credential change has to be auditable"
    assert secret not in str(entries)
    assert "api_key" in str(entries[0]["detail"]), "it should say a credential changed"


async def test_a_credential_that_cannot_be_decrypted_is_shown_as_unreadable(
    client, admin_headers, monkeypatch
):
    """A rotated encryption key. The admin has to be told to re-enter it — showing an
    empty box would read as "never configured" and they would not know to."""
    await client.patch("/api/v1/settings/helpdesk", headers=admin_headers,
                       json={"domain": "acme", "api_key": "fs-secret", "enabled": True})
    monkeypatch.setattr(get_settings(), "secrets_key", crypto.generate_key(), raising=False)

    body = (await client.get("/api/v1/settings/helpdesk", headers=admin_headers)).json()
    assert body["api_key_masked"] == "unreadable"
    assert body["ready"] is False


async def test_saving_without_credential_storage_is_a_deployment_error(
    client, admin_headers, monkeypatch
):
    """503, not 400. The administrator's form is correct; the deployment is missing a key,
    and telling them to fix their input would send them in circles."""
    monkeypatch.setattr(get_settings(), "secrets_key", None, raising=False)
    resp = await client.patch("/api/v1/settings/helpdesk", headers=admin_headers,
                              json={"domain": "acme", "api_key": "fs-secret"})
    assert resp.status_code == 503
    assert "ASTRA_SECRETS_KEY" in resp.json()["detail"]


# ── Who may touch it ───────────────────────────────────────────────────────


@pytest.mark.parametrize("method,path", [
    ("get", "/api/v1/settings/helpdesk"),
    ("patch", "/api/v1/settings/helpdesk"),
    ("post", "/api/v1/settings/helpdesk/verify"),
])
async def test_only_an_admin_may_touch_the_connection(client, user_headers, method, path):
    """A credential to the company's service desk is not a setting a regular user reads,
    let alone changes."""
    call = getattr(client, method)
    resp = await (call(path, headers=user_headers, json={})
                  if method in ("patch", "post") else call(path, headers=user_headers))
    assert resp.status_code == 403


async def test_one_org_cannot_see_another_orgs_connection(client, admin_headers,
                                                          session_factory, other_org):
    from app.models import HelpdeskSettings

    async with session_factory() as session:
        session.add(HelpdeskSettings(org_id=other_org.id, enabled=True, domain="secret-corp",
                                     api_key_encrypted=crypto.encrypt("theirs")))
        await session.commit()

    body = (await client.get("/api/v1/settings/helpdesk", headers=admin_headers)).json()
    assert body["domain"] != "secret-corp"
    assert body["ready"] is False


# ── Verifying ──────────────────────────────────────────────────────────────


async def test_verify_says_which_piece_is_missing(client, admin_headers):
    """"Not configured" sends an admin back to a form they have already mostly filled in."""
    first = (await client.post("/api/v1/settings/helpdesk/verify",
                               headers=admin_headers)).json()
    assert first["ok"] is False
    assert "turned off" in first["detail"]

    await client.patch("/api/v1/settings/helpdesk", headers=admin_headers,
                       json={"enabled": True})
    second = (await client.post("/api/v1/settings/helpdesk/verify",
                                headers=admin_headers)).json()
    assert "domain" in second["detail"]

    await client.patch("/api/v1/settings/helpdesk", headers=admin_headers,
                       json={"domain": "acme"})
    third = (await client.post("/api/v1/settings/helpdesk/verify",
                               headers=admin_headers)).json()
    assert "API key" in third["detail"]


async def test_a_successful_check_creates_no_ticket(client, admin_headers, monkeypatch):
    """An administrator can press this as often as they like without leaving test tickets
    in their own queue — which is the only reason it is safe to offer at all."""
    import httpx

    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url)))
        return httpx.Response(200, json={"ticket_fields": []})

    transport = httpx.MockTransport(handler)
    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient",
                        lambda *a, **k: real(*a, **{**k, "transport": transport}))

    await client.patch("/api/v1/settings/helpdesk", headers=admin_headers,
                       json={"domain": "acme", "api_key": "k", "enabled": True})
    result = (await client.post("/api/v1/settings/helpdesk/verify",
                                headers=admin_headers)).json()

    assert result["ok"] is True
    assert all(method == "GET" for method, _ in calls), "verification must never POST"
    assert all("/tickets" not in url for _, url in calls)

    body = (await client.get("/api/v1/settings/helpdesk", headers=admin_headers)).json()
    assert body["last_verified_at"] is not None
    assert body["last_error"] is None


async def test_a_rejected_key_is_reported_and_remembered(client, admin_headers, monkeypatch):
    import httpx

    transport = httpx.MockTransport(lambda r: httpx.Response(401, json={}))
    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient",
                        lambda *a, **k: real(*a, **{**k, "transport": transport}))

    await client.patch("/api/v1/settings/helpdesk", headers=admin_headers,
                       json={"domain": "acme", "api_key": "bad", "enabled": True})
    result = (await client.post("/api/v1/settings/helpdesk/verify",
                                headers=admin_headers)).json()

    assert result["ok"] is False
    assert "rejected" in result["detail"]
    body = (await client.get("/api/v1/settings/helpdesk", headers=admin_headers)).json()
    assert body["last_verified_at"] is None
    assert "rejected" in body["last_error"]


async def test_a_new_key_invalidates_the_previous_verification(client, admin_headers,
                                                               monkeypatch):
    """What the last check proved was about the old credential. Leaving the tick in place
    would show a connection as verified when nothing has tested it."""
    import httpx

    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient",
                        lambda *a, **k: real(*a, **{**k, "transport": transport}))

    await client.patch("/api/v1/settings/helpdesk", headers=admin_headers,
                       json={"domain": "acme", "api_key": "k1", "enabled": True})
    await client.post("/api/v1/settings/helpdesk/verify", headers=admin_headers)
    assert (await client.get("/api/v1/settings/helpdesk",
                             headers=admin_headers)).json()["last_verified_at"]

    await client.patch("/api/v1/settings/helpdesk", headers=admin_headers,
                       json={"api_key": "k2"})
    assert (await client.get("/api/v1/settings/helpdesk",
                             headers=admin_headers)).json()["last_verified_at"] is None


# ── Service level, independent of HTTP ─────────────────────────────────────


async def test_the_service_updates_and_verifies_directly(session_factory, admin_user,
                                                         monkeypatch):
    """Exercises the service without the API in front of it.

    Worth having on its own: the endpoints are a thin shell, and a bug in ordering — a
    credential written before the audit entry, a verification cleared after it is set —
    is easier to see here than through two layers of HTTP.
    """
    import httpx

    from app.schemas.helpdesk import HelpdeskSettingsUpdate
    from app.services.support.settings import HelpdeskSettingsService

    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient",
                        lambda *a, **k: real(*a, **{**k, "transport": transport}))

    async with session_factory() as session:
        user = await session.get(type(admin_user), admin_user.id)
        svc = HelpdeskSettingsService(session)

        blank = await svc.get(org_id=user.org_id)
        assert blank.ready is False

        saved = await svc.update(actor=user, payload=HelpdeskSettingsUpdate(
            domain="https://acme.freshservice.com/a/tickets",
            api_key="fs-secret-key-4321", enabled=True,
        ))
        assert saved.domain == "acme"
        assert saved.ready is True
        assert saved.api_key_masked.endswith("4321")

        ok, detail = await svc.verify(actor=user)
        assert ok is True and detail is None
        assert (await svc.get(org_id=user.org_id)).last_verified_at is not None


# ── The domain is a hostname template, not free text ───────────────────────


@pytest.mark.parametrize("hostile", [
    "10.128.0.1:8080?",         # "?" ends the authority, so ".freshservice.com" lands in
    "169.254.169.254:80?",      # the query string and the host becomes whatever was typed
    "attacker.com?",
    "[::1]:80?",
    "acme.freshservice.com.evil.com",
    "acme evil",
    "-acme",
])
async def test_a_domain_that_would_escape_the_template_is_refused(client, admin_headers,
                                                                  hostile):
    """SSRF. `base_url` is f"https://{domain}.freshservice.com", and POST /verify makes the
    request — so a domain that can terminate the authority early turns any org admin into a
    client of ASTRA's own network, with the response body read back to them."""
    resp = await client.patch("/api/v1/settings/helpdesk", headers=admin_headers,
                              json={"domain": hostile})
    assert resp.status_code == 422, f"{hostile!r} was accepted: {resp.text}"

    body = (await client.get("/api/v1/settings/helpdesk", headers=admin_headers)).json()
    assert body["domain"] is None, "a refused domain must not have been written"


async def test_every_accepted_domain_stays_under_freshservice_com(client, admin_headers):
    """The end-to-end version of the rule above: whatever survives validation must produce
    a host inside the one domain this connector is allowed to talk to."""
    import httpx as _httpx

    for given in ["acme", "acme-it", "ACME.freshservice.com", "acme/../..", "localhost#",
                  "https://a1.freshservice.com/a/tickets/12"]:
        resp = await client.patch("/api/v1/settings/helpdesk", headers=admin_headers,
                                  json={"domain": given})
        if resp.status_code != 200:
            continue
        domain = resp.json()["domain"]
        host = _httpx.URL(f"https://{domain}.freshservice.com/api/v2/tickets").host
        assert host.endswith(".freshservice.com"), f"{given!r} -> {host}"


# ── Revoking, and a broken deployment ──────────────────────────────────────


async def test_an_empty_api_key_revokes_the_saved_one(client, admin_headers):
    """An admin whose key leaked has to be able to take it out of our database. Turning the
    connector off leaves the ciphertext sitting there."""
    await client.patch("/api/v1/settings/helpdesk", headers=admin_headers,
                       json={"domain": "acme", "api_key": "fs-secret-key-9911",
                             "enabled": True})
    resp = await client.patch("/api/v1/settings/helpdesk", headers=admin_headers,
                              json={"api_key": ""})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["api_key_masked"] == ""
    assert body["ready"] is False


async def test_a_malformed_secrets_key_says_so_instead_of_500ing(client, admin_headers,
                                                                 monkeypatch):
    """Present-but-invalid is a deployment mistake, and it must not reach the admin as an
    opaque error. It reads exactly like "not configured" to `is_available`."""
    monkeypatch.setattr(get_settings(), "secrets_key", "not-a-fernet-key", raising=False)
    resp = await client.patch("/api/v1/settings/helpdesk", headers=admin_headers,
                              json={"domain": "acme", "api_key": "fs-secret-key-9911"})
    assert resp.status_code == 503, resp.text
    assert "ASTRA_SECRETS_KEY" in resp.json()["detail"]


async def test_a_whitespace_only_api_key_does_not_revoke(client, admin_headers):
    """A paste that went wrong is not a revocation. Only an explicit "" clears the key."""
    await client.patch("/api/v1/settings/helpdesk", headers=admin_headers,
                       json={"domain": "acme", "api_key": "fs-secret-key-9911",
                             "enabled": True})
    resp = await client.patch("/api/v1/settings/helpdesk", headers=admin_headers,
                              json={"api_key": "   "})
    assert resp.status_code == 200, resp.text
    assert resp.json()["ready"] is True, "the saved key must still be there"


async def test_a_failed_verify_is_audited(client, admin_headers, session_factory):
    """This endpoint makes an outbound request on the deployment's behalf against an
    admin-supplied domain. A run that failed is exactly the one an investigator needs to
    see, and it was the only path that recorded nothing at all."""
    from sqlalchemy import select

    from app.models import AuditLog

    resp = await client.post("/api/v1/settings/helpdesk/verify", headers=admin_headers)
    assert resp.json()["ok"] is False

    async with session_factory() as session:
        entry = (await session.execute(
            select(AuditLog).where(AuditLog.action == "helpdesk.settings.verify")
        )).scalars().one()
        assert entry.detail["ok"] is False
