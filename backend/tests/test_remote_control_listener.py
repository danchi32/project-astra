"""The listener: relay events become ASTRA's record of what happened.

No relay is mocked at the protocol level here — `RelayEvent` is the seam, and feeding
one in is exactly what the socket does. What these tests pin down is the mapping, which
is where the judgement lives.
"""
import base64
import json
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.security import hash_opaque_token
from app.models import AuditLog, Device, RemoteSession, RemoteSessionStatus, User
from app.models.base import utcnow
from app.services.entitlements import REMOTE_CONTROL
from app.services.meshcentral import (
    MSG_DESKTOP_ENDED,
    MSG_DESKTOP_REFUSED,
    MSG_DESKTOP_STARTED,
    REQUIRED_RELAY_CONSENT_TIMEOUT,
    MeshCentralClient,
    MeshCentralNotConfigured,
    RelayEvent,
)
from app.services.remote_control import CONSENT_TIMEOUT, RemoteControlService
from app.services.remote_control_listener import RemoteControlListener

NODE = "node//abc123"
REASON = "Teams won't launch and the restart didn't fix it"


def _event(msgid, *, node_id=NODE, session_id=None, args=None) -> RelayEvent:
    return RelayEvent.from_message({
        "msgid": msgid, "nodeid": node_id, "sessionid": session_id,
        "userid": "user//astraadmin", "msgArgs": args or [],
    })


async def _device(session_factory, org, machine="l-1", node_id=NODE) -> uuid.UUID:
    async with session_factory() as s:
        device = Device(
            org_id=org.id, hostname="LST-PC", machine_id=machine,
            os_version="Windows 11", agent_version="0.6.4",
            token_hash=hash_opaque_token(f"tok-{machine}"), last_seen_at=utcnow(),
            meshcentral_node_id=node_id,
        )
        s.add(device)
        await s.commit()
        return device.id


async def _grant(session_factory, org):
    async with session_factory() as s:
        from app.models import Organization
        o = await s.get(Organization, org.id)
        o.entitlement_overrides = {REMOTE_CONTROL: True}
        await s.commit()


async def _pending(session_factory, org, admin_user, device_id) -> uuid.UUID:
    async with session_factory() as s:
        actor = await s.get(User, admin_user.id)
        return (await RemoteControlService(s).request(
            actor=actor, device_id=device_id, reason=REASON)).id


# ── The invariant the whole design rests on ───────────────────────────────


def test_the_relay_must_time_out_later_than_astra_does():
    """MeshCentral reports a decline and a timeout with the same id.

    So "the user pressed Deny" is only distinguishable from "the user never answered" if
    ASTRA's own window closes first — then a refusal arriving afterwards lands on a
    session already recorded as NO_RESPONSE and is dropped.

    Reverse the two and every unanswered prompt becomes a refusal: the exact bug the
    spike surfaced, silently reintroduced by editing a config file. Hence this test,
    which fails the moment somebody shortens the relay's window or lengthens ASTRA's.
    """
    assert REQUIRED_RELAY_CONSENT_TIMEOUT > CONSENT_TIMEOUT.total_seconds() * 2, (
        "The relay's consentTimeout must sit well clear of ASTRA's, so that in practice "
        "it never fires and a refusal event can only mean a person pressed Deny."
    )


# ── Mapping events onto sessions ──────────────────────────────────────────


async def test_a_started_desktop_records_consent_and_goes_active(
    session_factory, org, admin_user
):
    """There is no separate "accepted" event — the relay only starts a desktop after the
    person agreed, so the start IS the consent."""
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "l-1")
    session_id = await _pending(session_factory, org, admin_user, device_id)

    listener = RemoteControlListener(session_factory, MeshCentralClient())
    assert await listener.handle(_event(MSG_DESKTOP_STARTED, session_id="5tiwtqy9xif"))

    async with session_factory() as s:
        row = await s.get(RemoteSession, session_id)
        assert row.status is RemoteSessionStatus.ACTIVE
        assert row.responded_at is not None
        assert row.provider_session_id == "5tiwtqy9xif"


async def test_a_refusal_while_the_prompt_is_live_is_a_decline(
    session_factory, org, admin_user
):
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "l-2")
    session_id = await _pending(session_factory, org, admin_user, device_id)

    listener = RemoteControlListener(session_factory, MeshCentralClient())
    assert await listener.handle(_event(MSG_DESKTOP_REFUSED))

    async with session_factory() as s:
        assert (await s.get(RemoteSession, session_id)).status is RemoteSessionStatus.DECLINED


async def test_a_refusal_arriving_after_the_sweep_does_not_rewrite_no_response(
    session_factory, org, admin_user
):
    """The invariant above, exercised end to end.

    ASTRA retires the prompt first. The relay's own refusal turns up later — and must
    find nothing to change, or the technician is told their customer said no.
    """
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "l-3")
    session_id = await _pending(session_factory, org, admin_user, device_id)

    async with session_factory() as s:
        row = await s.get(RemoteSession, session_id)
        row.requested_at = utcnow() - CONSENT_TIMEOUT - timedelta(seconds=1)
        await s.commit()
    async with session_factory() as s:
        assert await RemoteControlService(s).expire_stale() == 1

    listener = RemoteControlListener(session_factory, MeshCentralClient())
    assert await listener.handle(_event(MSG_DESKTOP_REFUSED)) is False

    async with session_factory() as s:
        row = await s.get(RemoteSession, session_id)
        assert row.status is RemoteSessionStatus.NO_RESPONSE


async def test_an_ended_desktop_closes_the_session(session_factory, org, admin_user):
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "l-4")
    session_id = await _pending(session_factory, org, admin_user, device_id)

    listener = RemoteControlListener(session_factory, MeshCentralClient())
    await listener.handle(_event(MSG_DESKTOP_STARTED, session_id="abc"))
    assert await listener.handle(_event(MSG_DESKTOP_ENDED, args=["abc", "1.2.3.4", 31]))

    async with session_factory() as s:
        row = await s.get(RemoteSession, session_id)
        assert row.status is RemoteSessionStatus.ENDED
        assert row.ended_at is not None

    async with session_factory() as s:
        actions = (await s.execute(select(AuditLog.action))).scalars().all()
        assert "remote_session.end" in actions


async def test_events_for_an_unknown_device_are_dropped(session_factory, org, admin_user):
    """Somebody else's relay traffic, or a device ASTRA has never mapped. Not an error."""
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "l-5")
    session_id = await _pending(session_factory, org, admin_user, device_id)

    listener = RemoteControlListener(session_factory, MeshCentralClient())
    assert await listener.handle(_event(MSG_DESKTOP_REFUSED, node_id="node//nope")) is False

    async with session_factory() as s:
        assert (await s.get(RemoteSession, session_id)).status is RemoteSessionStatus.PENDING


async def test_unrelated_relay_chatter_is_ignored(session_factory, org, admin_user):
    """The stream carries far more than this feature cares about."""
    await _grant(session_factory, org)
    device_id = await _device(session_factory, org, "l-6")
    await _pending(session_factory, org, admin_user, device_id)

    listener = RemoteControlListener(session_factory, MeshCentralClient())
    for msgid in (1, 42, 142, None):
        assert await listener.handle(_event(msgid)) is False


# ── The client's own parsing ──────────────────────────────────────────────


def test_the_duration_is_read_off_the_event_rather_than_measured():
    """The relay already counted the seconds and the bytes. Re-deriving them from our own
    timestamps would disagree with the relay's own log the first time a clock drifted."""
    ev = RelayEvent.from_message({
        "msgid": MSG_DESKTOP_ENDED, "nodeid": NODE,
        "msgArgs": ["p9z7weu7ycq", "10.21.5.104", "10.21.5.104", 31],
    })
    assert ev.seconds == 31


def test_a_client_with_no_relay_configured_says_so_rather_than_failing():
    """Most deployments have no relay. That is a configuration fact, not a fault."""
    client = MeshCentralClient()
    assert client.configured is False


def test_the_control_url_is_derived_from_the_relay_url():
    client = MeshCentralClient(
        url="https://remote.example.com/", user="u", token="t")
    assert client._control_url() == "wss://remote.example.com/control.ashx"
    assert MeshCentralClient(
        url="http://localhost:8443", user="u", token="t"
    )._control_url() == "ws://localhost:8443/control.ashx"


def test_the_token_is_sent_as_credentials_not_as_a_password():
    """base64 of user and token, comma separated — the account password never travels."""
    import base64

    client = MeshCentralClient(url="https://x", user="~t:abc", token="secret")
    header = client._auth_header()["x-meshauth"]
    user_b64, token_b64 = header.split(",")
    assert base64.b64decode(user_b64).decode() == "~t:abc"
    assert base64.b64decode(token_b64).decode() == "secret"


# ── The viewer link ───────────────────────────────────────────────────────
#
# The piece that keeps MeshCentral invisible: the technician clicks a button in the
# ASTRA portal and lands on a device's desktop, never meeting the relay's login page.
# Verified against a live relay while it was written — a cookie signed with the wrong
# key gets the login page, which is the property these tests stand in for.

COOKIE_KEY = "ab" * 80        # 80 bytes, the length the relay requires
NODE_ID = "node//abc$123@xyz"


def _client():
    return MeshCentralClient(
        url="https://relay.example.com", user="~t:u", token="t", cookie_key=COOKIE_KEY)


def test_a_viewer_link_opens_one_device_and_nothing_else():
    url = _client().viewer_url(node_id=NODE_ID, user_id="user//tech")
    assert url.startswith("https://relay.example.com/?login=")
    # viewmode=11 is the desktop tab; hide=31 strips the relay's own chrome, so what
    # lands in the portal's iframe is a screen rather than somebody else's product.
    assert "viewmode=11" in url and "hide=31" in url
    # gotonode is the BARE id — no "node//" prefix — because the relay's web app builds
    # it from `_id.split('/')[2]`; the prefixed form fails to resolve and the desktop
    # never connects. The special characters are still url-encoded ($ -> %24, @ -> %40).
    assert "gotonode=abc%24123%40xyz" in url
    assert "node%2F%2F" not in url


def test_the_cookie_is_encrypted_with_the_shared_key_not_merely_encoded():
    """A relay that accepted a self-signed cookie would let anyone who can guess the
    format onto any device. Confirmed live: a cookie signed with a different key is
    refused and the browser gets the login page."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    cookie = _client().encode_login_cookie("user//tech")
    raw = base64.b64decode(cookie.replace("@", "+").replace("$", "/"))
    iv, tag, ciphertext = raw[:12], raw[12:28], raw[28:]

    payload = json.loads(
        AESGCM(bytes.fromhex(COOKIE_KEY)[:32]).decrypt(iv, ciphertext + tag, None))
    assert payload["u"] == "user//tech"
    assert isinstance(payload["time"], int)

    # The wrong key must not open it — and the failure is an authentication-tag
    # mismatch, not a decode error, which is the difference between "this was signed by
    # somebody else" and "this was malformed".
    from cryptography.exceptions import InvalidTag

    with pytest.raises(InvalidTag):
        AESGCM(bytes.fromhex("cd" * 32)).decrypt(iv, ciphertext + tag, None)


def test_every_link_is_unique_even_for_the_same_device():
    """A fresh random IV per link. Identical URLs would be shareable and replayable."""
    client = _client()
    links = {client.viewer_url(node_id=NODE_ID, user_id="user//tech") for _ in range(5)}
    assert len(links) == 5


def test_no_link_is_issued_without_a_key():
    """A deployment with no relay key must refuse rather than hand out a URL that
    silently drops the technician on a login page they have no account for."""
    client = MeshCentralClient(
        url="https://relay.example.com", user="u", token="t", cookie_key=None)
    with pytest.raises(MeshCentralNotConfigured):
        client.viewer_url(node_id=NODE_ID, user_id="user//tech")
