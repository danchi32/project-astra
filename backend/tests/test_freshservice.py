"""Filing a ticket into the customer's own Freshservice.

The endpoint and field shapes were taken from the API reference and a real instance's field
schema, so what these tests guard is not "did I remember the API" — it is the handful of
places where being wrong is invisible: a ticket attributed to nobody, a 201 reported as a
number we never received, a credential readable in a database dump.
"""
import base64
import json
import uuid

import httpx
import pytest

from app.core import crypto
from app.core.config import get_settings
from app.models import HelpdeskSettings
from app.services.support.connector import TicketError, TicketRequest
from app.services.support.factory import build_connector, category_for
from app.services.support.freshservice import FreshserviceConnector, ticket_url

KEY = None  # set per-test; Fernet keys must be generated, not hardcoded


def _request(**kw) -> TicketRequest:
    return TicketRequest(
        requester_email=kw.pop("requester_email", "priya@acme.com"),
        subject=kw.pop("subject", "[ASTRA] laptop slow — PC-1"),
        description_html=kw.pop("description_html", "<p>dossier</p>"),
        **kw,
    )


def _connector(monkeypatch, handler, **kw) -> FreshserviceConnector:
    transport = httpx.MockTransport(handler)
    real = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs.setdefault("transport", transport)
        return real(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)
    return FreshserviceConnector(domain=kw.pop("domain", "acme"),
                                 api_key=kw.pop("api_key", "key-123"), **kw)


def _created(ticket_id: int = 4242):
    return lambda request: httpx.Response(201, json={"ticket": {"id": ticket_id}})


# ── The request we send ────────────────────────────────────────────────────


async def test_it_posts_the_documented_shape(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.read())
        return httpx.Response(201, json={"ticket": {"id": 4242}})

    conn = _connector(monkeypatch, handler)
    result = await conn.create_ticket(_request())

    assert seen["url"] == "https://acme.freshservice.com/api/v2/tickets"
    assert result.external_id == "4242"
    # Basic auth with the key as username and any password — "X" by convention.
    assert seen["auth"] == "Basic " + base64.b64encode(b"key-123:X").decode()

    body = seen["body"]
    assert body["email"] == "priya@acme.com"
    assert body["status"] == 2, "tickets are created Open"
    assert body["priority"] == 1
    assert "astra" in body["tags"], "their reporting must be able to find ASTRA's tickets"


async def test_optional_routing_is_omitted_rather_than_guessed(monkeypatch):
    """An unset workspace, source, group or category must not be sent as a made-up value.
    A wrong workspace files the ticket where nobody is watching."""
    seen = {}
    conn = _connector(monkeypatch, lambda r: (seen.update(body=json.loads(r.read()))
                                              or httpx.Response(201, json={"ticket": {"id": 1}})))
    await conn.create_ticket(_request())
    for field in ("workspace_id", "source", "group_id", "category", "sub_category"):
        assert field not in seen["body"], field


async def test_configured_routing_is_sent(monkeypatch):
    seen = {}
    conn = _connector(
        monkeypatch,
        lambda r: (seen.update(body=json.loads(r.read()))
                   or httpx.Response(201, json={"ticket": {"id": 1}})),
        workspace_id=1, source=2, group_id=99,
    )
    await conn.create_ticket(_request(category="Software", sub_category="Office 365"))
    assert seen["body"]["workspace_id"] == 1
    assert seen["body"]["source"] == 2
    assert seen["body"]["group_id"] == 99
    assert seen["body"]["category"] == "Software"
    assert seen["body"]["sub_category"] == "Office 365"


@pytest.mark.parametrize("given,expected", [
    ("low", 1), ("medium", 2), ("high", 3), ("urgent", 4),
])
async def test_priority_maps_to_freshservice_ids(monkeypatch, given, expected):
    seen = {}
    conn = _connector(monkeypatch,
                      lambda r: (seen.update(body=json.loads(r.read()))
                                 or httpx.Response(201, json={"ticket": {"id": 1}})))
    await conn.create_ticket(_request(priority=given))
    assert seen["body"]["priority"] == expected


async def test_an_unknown_priority_falls_back_to_the_orgs_default(monkeypatch):
    """ASTRA does not invent urgency. An unrecognised value lands on what the org chose,
    not on something more alarming."""
    seen = {}
    conn = _connector(monkeypatch,
                      lambda r: (seen.update(body=json.loads(r.read()))
                                 or httpx.Response(201, json={"ticket": {"id": 1}})),
                      default_priority=2)
    await conn.create_ticket(_request(priority="catastrophic"))
    assert seen["body"]["priority"] == 2


async def test_a_full_domain_is_accepted_as_well_as_a_subdomain(monkeypatch):
    """An admin will paste whatever is in their address bar."""
    seen = {}
    conn = _connector(monkeypatch,
                      lambda r: (seen.update(url=str(r.url))
                                 or httpx.Response(201, json={"ticket": {"id": 1}})),
                      domain="acme.freshservice.com")
    await conn.create_ticket(_request())
    assert seen["url"] == "https://acme.freshservice.com/api/v2/tickets"


# ── Never file a ticket nobody owns ────────────────────────────────────────


async def test_it_refuses_to_file_without_a_requester(monkeypatch):
    """Freshservice would happily attribute this to whoever the API key belongs to. The
    employee would then never hear back about their own problem, and the customer's SLA
    and CSAT reporting would be measuring the wrong person."""
    conn = _connector(monkeypatch, _created())
    with pytest.raises(TicketError, match="requester"):
        await conn.create_ticket(_request(requester_email=""))


# ── Failures that must not look like success ───────────────────────────────


@pytest.mark.parametrize("handler,expect", [
    (lambda r: httpx.Response(401, json={}), "API key was rejected"),
    (lambda r: httpx.Response(403, json={}), "lacks permission"),
    (lambda r: httpx.Response(404, json={}), "no Freshservice instance"),
    (lambda r: httpx.Response(429, json={}), "rate limit"),
])
async def test_common_rejections_are_explained_not_just_numbered(monkeypatch, handler, expect):
    """These land in last_error and in the logs. "400 Bad Request" on its own has cost
    enough debugging hours to be worth the extra lines."""
    conn = _connector(monkeypatch, handler)
    with pytest.raises(TicketError, match=expect):
        await conn.create_ticket(_request())


async def test_a_field_rejection_names_the_field(monkeypatch):
    """The single most useful failure to surface: an org has made something mandatory that
    we are not sending, and Freshservice says exactly which."""
    conn = _connector(monkeypatch, lambda r: httpx.Response(400, json={
        "errors": [{"field": "category", "message": "It should be a valid category"}]
    }))
    with pytest.raises(TicketError, match="category"):
        await conn.create_ticket(_request())


async def test_a_201_without_an_id_is_an_error(monkeypatch):
    """Otherwise the user is told "I've raised ticket #None" and has nothing to chase."""
    conn = _connector(monkeypatch, lambda r: httpx.Response(201, json={"ticket": {}}))
    with pytest.raises(TicketError, match="no id"):
        await conn.create_ticket(_request())


async def test_a_201_that_is_not_json_is_an_error(monkeypatch):
    """A proxy or a login page can return 201 with HTML. Treating that as a filed ticket
    would tell the user a number that was never issued."""
    conn = _connector(monkeypatch, lambda r: httpx.Response(201, text="<html>hi</html>"))
    with pytest.raises(TicketError, match="could not read"):
        await conn.create_ticket(_request())


async def test_a_rejection_that_is_not_json_still_carries_the_body(monkeypatch):
    """Non-JSON errors are exactly the ones nobody can diagnose from a status code — a
    WAF block, an expired trial notice, an HTML error page."""
    conn = _connector(monkeypatch,
                      lambda r: httpx.Response(400, text="Account suspended by admin"))
    with pytest.raises(TicketError, match="Account suspended"):
        await conn.create_ticket(_request())


async def test_a_rejection_with_a_description_is_surfaced(monkeypatch):
    conn = _connector(monkeypatch, lambda r: httpx.Response(
        400, json={"description": "Validation failed"}))
    with pytest.raises(TicketError, match="Validation failed"):
        await conn.create_ticket(_request())


async def test_a_network_failure_is_a_ticket_error_not_a_crash(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("dns failure")

    conn = _connector(monkeypatch, handler)
    with pytest.raises(TicketError, match="Could not reach"):
        await conn.create_ticket(_request())


def test_the_agent_url_points_at_the_ticket():
    assert ticket_url("acme", "4242") == "https://acme.freshservice.com/a/tickets/4242"


# ── The credential ─────────────────────────────────────────────────────────


def test_a_credential_round_trips_but_is_not_stored_in_the_clear(monkeypatch):
    monkeypatch.setattr(get_settings(), "secrets_key", crypto.generate_key(), raising=False)
    secret = "fs-api-key-abc123"
    stored = crypto.encrypt(secret)
    assert secret not in stored
    assert crypto.decrypt(stored) == secret


def test_storing_a_credential_without_a_key_is_refused(monkeypatch):
    """Falling back to plaintext would be the worst outcome: a secret nobody knows is a
    secret, sitting in a column."""
    monkeypatch.setattr(get_settings(), "secrets_key", None, raising=False)
    with pytest.raises(crypto.CryptoUnavailable):
        crypto.encrypt("fs-api-key")


def test_a_rotated_key_reports_rather_than_returning_nothing(monkeypatch):
    """Silently treating an undecryptable credential as absent would look identical to
    "this org never connected a helpdesk", and the admin who did would never find out."""
    monkeypatch.setattr(get_settings(), "secrets_key", crypto.generate_key(), raising=False)
    stored = crypto.encrypt("fs-api-key")
    monkeypatch.setattr(get_settings(), "secrets_key", crypto.generate_key(), raising=False)
    with pytest.raises(crypto.DecryptionFailed):
        crypto.decrypt(stored)


def test_a_malformed_key_is_a_deployment_error_not_a_missing_one(monkeypatch):
    """"Key is garbage" and "no key set" produce very different fixes. Collapsing them
    would send an operator looking for a config value that is already there."""
    monkeypatch.setattr(get_settings(), "secrets_key", "not-a-fernet-key", raising=False)
    with pytest.raises(crypto.CryptoUnavailable, match="not a valid Fernet key"):
        crypto.encrypt("anything")


def test_encrypting_nothing_is_refused():
    """An empty credential round-trips to an empty credential, and the integration then
    fails later at the API with something far less obvious."""
    with pytest.raises(ValueError):
        crypto.encrypt("")


def test_is_available_reflects_configuration(monkeypatch):
    monkeypatch.setattr(get_settings(), "secrets_key", None, raising=False)
    assert crypto.is_available() is False
    monkeypatch.setattr(get_settings(), "secrets_key", crypto.generate_key(), raising=False)
    assert crypto.is_available() is True


def test_masking_a_short_or_missing_secret_reveals_nothing():
    assert crypto.mask(None) == ""
    assert crypto.mask("") == ""
    assert "abc" not in crypto.mask("abc")


def test_a_masked_credential_is_recognisable_but_unusable():
    masked = crypto.mask("fs-api-key-abcd1234")
    assert "fs-api-key" not in masked
    assert masked.endswith("1234")


# ── Building it for an organization ────────────────────────────────────────


async def _settings(session, org_id, **kw) -> HelpdeskSettings:
    row = HelpdeskSettings(org_id=org_id, **kw)
    session.add(row)
    await session.flush()
    return row


async def test_a_configured_org_gets_a_connector(session_factory, admin_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "secrets_key", crypto.generate_key(), raising=False)
    async with session_factory() as session:
        await _settings(session, admin_user.org_id, enabled=True, domain="acme",
                        api_key_encrypted=crypto.encrypt("k"), workspace_id=1)
        connector = await build_connector(session, admin_user.org_id)
    assert isinstance(connector, FreshserviceConnector)
    assert connector.workspace_id == 1


@pytest.mark.parametrize("kw", [
    {},                                                    # no row at all
    {"enabled": False, "domain": "acme", "api_key_encrypted": "x"},
    {"enabled": True, "domain": None, "api_key_encrypted": "x"},
    {"enabled": True, "domain": "acme", "api_key_encrypted": None},
])
async def test_an_unconfigured_org_gets_nothing(session_factory, admin_user, monkeypatch, kw):
    """Every one of these is a reason the assistant must not offer to raise a ticket.
    Offering and then failing is worse than never offering — the user has already been
    told help is on the way."""
    monkeypatch.setattr(get_settings(), "secrets_key", crypto.generate_key(), raising=False)
    async with session_factory() as session:
        if kw:
            await _settings(session, admin_user.org_id, **kw)
        assert await build_connector(session, admin_user.org_id) is None


async def test_an_undecryptable_credential_disables_the_integration_loudly(
    session_factory, admin_user, monkeypatch, caplog
):
    monkeypatch.setattr(get_settings(), "secrets_key", crypto.generate_key(), raising=False)
    async with session_factory() as session:
        await _settings(session, admin_user.org_id, enabled=True, domain="acme",
                        api_key_encrypted=crypto.encrypt("k"))
        monkeypatch.setattr(get_settings(), "secrets_key", crypto.generate_key(), raising=False)
        with caplog.at_level("ERROR"):
            connector = await build_connector(session, admin_user.org_id)

    assert connector is None
    assert "could not be decrypted" in caplog.text


async def test_an_unknown_provider_is_refused(session_factory, admin_user, monkeypatch, caplog):
    monkeypatch.setattr(get_settings(), "secrets_key", crypto.generate_key(), raising=False)
    async with session_factory() as session:
        await _settings(session, admin_user.org_id, enabled=True, provider="servicenow",
                        domain="acme", api_key_encrypted=crypto.encrypt("k"))
        with caplog.at_level("ERROR"):
            assert await build_connector(session, admin_user.org_id) is None
    assert "Unsupported helpdesk provider" in caplog.text


# ── Category mapping ───────────────────────────────────────────────────────


def test_a_mapped_action_files_into_the_orgs_own_category():
    settings = HelpdeskSettings(
        org_id=uuid.uuid4(),
        category_map={"restart_outlook": {"category": "Software",
                                          "sub_category": "Office 365"}},
    )
    assert category_for(settings, "restart_outlook") == ("Software", "Office 365")


@pytest.mark.parametrize("settings,action", [
    (None, "restart_outlook"),
    (HelpdeskSettings(org_id=uuid.uuid4(), category_map=None), "restart_outlook"),
    (HelpdeskSettings(org_id=uuid.uuid4(), category_map={"flush_dns": {}}), "restart_teams"),
    (HelpdeskSettings(org_id=uuid.uuid4(), category_map={"x": "not-a-dict"}), "x"),
])
def test_an_unmapped_action_files_unclassified(settings, action):
    """Every helpdesk's category tree is its own. A guessed category puts the ticket in
    front of the wrong team, which is worse than putting it in front of triage."""
    assert category_for(settings, action) == (None, None)
