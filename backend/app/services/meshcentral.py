"""Talking to the MeshCentral relay.

Everything in this module was settled by probing a live server rather than by reading
docs, because the protocol has three properties that a reasonable person would guess
wrong:

1. It is a WebSocket, not REST. One connection to /control.ashx carries JSON messages in
   both directions, and the server pushes without being asked — `serverinfo` and
   `traceinfo` arrive on connect, before any command is sent.

2. `responseid` is NOT echoed back. There is no built-in way to match a reply to the
   command that caused it, so a caller that needs an answer reads the stream until a
   message of the expected `action` arrives. That is why commands here are few and
   coarse: a chatty request/response client over this protocol would be guesswork.

3. Outcomes arrive as EVENTS, identified by a numeric `msgid`. Never match on `msg` —
   that field is English prose that a MeshCentral upgrade or a translation would change
   underneath us. The ids below are the contract.

Authentication is a login token, passed as an `x-meshauth` header. The account password
never appears here and must never be put in the environment: a token can be revoked from
the MeshCentral account page without changing anything else.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import ssl
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ── Event ids ─────────────────────────────────────────────────────────────
# Read off a live server. Stable numbers; the prose beside them is what that server
# happened to render in English, kept only so the next reader can recognise them.

#: "Started desktop session <id> from <ip> to <ip>" — the technician is connected.
MSG_DESKTOP_STARTED = 15

#: "Ended desktop session <id> ... N second(s)" — carries `bytesin`/`bytesout` too, which
#: is the session accounting ASTRA would otherwise have to measure for itself.
MSG_DESKTOP_ENDED = 11

#: "Failed to start remote desktop after local user rejected" — and this is the one to be
#: careful with. MeshCentral reports a DECLINE and a TIMEOUT with the same id, because to
#: it they are the same outcome. They are not the same event to a technician, so ASTRA
#: must have already decided which happened before this arrives. See CONSENT_HEADROOM.
MSG_DESKTOP_REFUSED = 34

#: MeshCentral's own consent window must be far longer than ASTRA's, so that in practice
#: its timer never fires. Then MSG_DESKTOP_REFUSED can only mean a person pressed Deny,
#: and a prompt nobody answered is retired by ASTRA's own sweep as NO_RESPONSE.
#:
#: Get this backwards — MeshCentral timing out first — and every unanswered prompt is
#: recorded as a refusal, which is the exact bug the spike surfaced and this whole design
#: exists to avoid. `consentTimeout` in the relay's config.json must be at least this.
REQUIRED_RELAY_CONSENT_TIMEOUT = 600


#: What the relay's own code puts in a login cookie: the user it logs you in as, and an
#: access level. Read off webserver.js rather than documentation — `{u: userid, a: 3}` is
#: the shape the relay builds for its own token logins, so it is the shape it expects.
_COOKIE_ACCESS_LEVEL = 3

#: The relay refuses a login cookie older than an hour. ASTRA hands out far shorter ones
#: — a viewer URL is for a session starting now — but the ceiling is the relay's and this
#: is it, so nothing here may assume a longer life.
COOKIE_MAX_AGE_SECONDS = 3600

#: The relay user id, resolved from the token once and cached for the process — it does
#: not change for a given token. Module-level so every client instance shares one lookup.
_RESOLVED_USER_ID: str | None = None


class MeshCentralError(Exception):
    pass


class MeshCentralNotConfigured(MeshCentralError):
    """No relay is configured for this deployment.

    Its own type because it is not a failure of the relay — there isn't one. The API
    turns it into "remote control isn't set up here" rather than a 500 that reads as a
    bug somebody should investigate.
    """


@dataclass(frozen=True)
class RelayEvent:
    """One line from the relay's event stream, reduced to what ASTRA acts on."""

    msgid: int | None
    node_id: str | None
    user_id: str | None
    session_id: str | None
    seconds: int | None
    raw: dict[str, Any]

    @classmethod
    def from_message(cls, msg: dict[str, Any]) -> RelayEvent:
        # `msgArgs` positions vary per event; the duration on a desktop-ended event is
        # the one value worth pulling out, and it is the last numeric argument.
        seconds = None
        for arg in reversed(msg.get("msgArgs") or []):
            if isinstance(arg, (int, float)):
                seconds = int(arg)
                break
        return cls(
            msgid=msg.get("msgid"),
            node_id=msg.get("nodeid"),
            user_id=msg.get("userid"),
            session_id=msg.get("sessionid"),
            seconds=seconds,
            raw=msg,
        )


class MeshCentralClient:
    """A connection to the relay's control channel.

    Deliberately thin. The relay is the authority on what is happening to a device;
    ASTRA's job is to authorise it, record it, and show it — not to reimplement it.
    """

    def __init__(
        self,
        *,
        url: str | None = None,
        user: str | None = None,
        token: str | None = None,
        cookie_key: str | None = None,
        insecure_tls: bool | None = None,
    ) -> None:
        settings = get_settings()
        self.url = url or settings.meshcentral_url
        self.user = user or settings.meshcentral_user
        self.token = token or settings.meshcentral_token
        self.cookie_key = cookie_key or settings.meshcentral_cookie_key
        self.user_id = settings.meshcentral_user_id
        self.insecure_tls = (
            settings.meshcentral_insecure_tls if insecure_tls is None else insecure_tls
        )

    @property
    def configured(self) -> bool:
        return bool(self.url and self.user and self.token)

    def _require(self) -> None:
        if not self.configured:
            raise MeshCentralNotConfigured(
                "Remote control is not set up on this deployment."
            )

    def _control_url(self) -> str:
        base = (self.url or "").rstrip("/")
        scheme = "wss://" if base.startswith("https://") else "ws://"
        return scheme + base.split("://", 1)[1] + "/control.ashx"

    def _auth_header(self) -> dict[str, str]:
        packed = (
            base64.b64encode((self.user or "").encode()).decode()
            + ","
            + base64.b64encode((self.token or "").encode()).decode()
        )
        return {"x-meshauth": packed}

    def _ssl_context(self) -> ssl.SSLContext | None:
        if not self._control_url().startswith("wss://"):
            return None
        ctx = ssl.create_default_context()
        if self.insecure_tls:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        return ctx

    @asynccontextmanager
    async def connect(self, *, open_timeout: float = 15.0) -> AsyncIterator[Any]:
        """An open control channel. The caller reads and writes JSON."""
        self._require()
        import websockets

        async with websockets.connect(
            self._control_url(),
            ssl=self._ssl_context(),
            additional_headers=self._auth_header(),
            open_timeout=open_timeout,
        ) as ws:
            yield ws

    # -- Provisioning the endpoint agent ---------------------------------------

    def agent_download_url(self, mesh_id: str) -> str:
        """Where a device fetches the remote-support agent for one device group.

        The relay builds this executable per group, with the server URL, the group id and
        the server's certificate hash already inside it — so the device downloads one file
        and needs no configuration alongside it.

        Nothing is bundled into the ASTRA installer, and that is the point. The relay is
        what compiles and code-signs this binary; a copy vendored into ASTRA's installer
        would go stale against the relay's certificate, would have to be byte-identical
        across organisations that need different group ids, and would put a remote-access
        executable on the disk of every customer including those who never bought remote
        control. Fetching on demand has none of those problems.

        `id=4` is the relay's Windows x64 background-service build.

        The mesh id here is the BARE id, with any "mesh//" prefix stripped — and that is
        the whole of a bug that cost real time. Everywhere else the id is stored and used
        with its prefix (the org column, the viewer URL's gotonode), but this one relay
        endpoint, /meshagents, matches on the bare id and answers 401 for the prefixed
        form. A prefixed id here means every device's download fails Unauthorized, the
        agent logs "could not install the remote support agent", and nothing provisions —
        with the endpoint otherwise looking perfectly configured.
        """
        self._require()
        base = (self.url or "").rstrip("/")
        bare = mesh_id.removeprefix("mesh//")
        return (
            f"{base}/meshagents?id=4"
            f"&meshid={quote(bare, safe='')}&installflags=0"
        )

    # -- The viewer URL --------------------------------------------------------

    def encode_login_cookie(self, user_id: str) -> str:
        """Mint the relay's own login cookie, without going through its login page.

        This is the piece that keeps MeshCentral invisible. The technician clicks a
        button in the ASTRA portal and lands on a device's desktop; they never see, and
        never need an account on, the relay.

        The format is the relay's, reproduced exactly — AES-256-GCM over the JSON, with
        the first 32 bytes of the shared key, and `+` and `/` swapped for `@` and `$` so
        the result survives a query string. `time` is checked on the other side, which is
        what bounds how long a minted URL stays good.
        """
        if not self.cookie_key:
            raise MeshCentralNotConfigured(
                "No relay cookie key is configured, so viewer links cannot be issued."
            )
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        key = bytes.fromhex(self.cookie_key)[:32]
        payload = json.dumps(
            {"u": user_id, "a": _COOKIE_ACCESS_LEVEL, "time": int(time.time())},
            separators=(",", ":"),
        ).encode()
        iv = os.urandom(12)
        sealed = AESGCM(key).encrypt(iv, payload, None)
        # AESGCM appends the 16-byte tag; the relay expects it in the middle.
        ciphertext, tag = sealed[:-16], sealed[-16:]
        raw = base64.b64encode(iv + tag + ciphertext).decode()
        return raw.replace("+", "@").replace("/", "$")

    def viewer_url(self, *, node_id: str, user_id: str) -> str:
        """A link that opens one device's desktop and nothing else.

        `viewmode=11` is the relay's desktop tab and `hide=31` strips its chrome — the
        toolbar, the device list, the other tabs — so what lands in the ASTRA portal's
        iframe is a screen, not somebody else's product.
        """
        self._require()
        cookie = self.encode_login_cookie(user_id)
        base = (self.url or "").rstrip("/")
        return (
            f"{base}/?login={quote(cookie, safe='')}"
            f"&gotonode={quote(node_id, safe='')}&viewmode=11&hide=31"
        )

    async def ping(self) -> dict[str, Any]:
        """Prove the relay is reachable and the token still works.

        Returns the `userinfo` the relay answers with, which also says whether the token
        carries the rights this integration needs. Used by the listener at startup and
        worth an operator-facing health check later.
        """
        async with self.connect() as ws:
            await ws.send(json.dumps({"action": "userinfo"}))
            for _ in range(10):
                msg = json.loads(await ws.recv())
                if msg.get("action") == "userinfo":
                    return msg.get("userinfo", {})
        raise MeshCentralError("The relay did not identify itself.")

    async def resolve_user_id(self) -> str | None:
        """The relay user id the viewer URL must log in as (e.g. "user//astraadmin").

        This is NOT `self.user`. That is the login-token username (`~t:...`) the control
        channel authenticates with; the cookie's `u` field has to be the id of the USER
        that token belongs to, and the relay drops the viewer to its login page for
        anything else — silently, because the cookie itself decodes fine.

        Configured value wins; otherwise ask the relay once (userinfo carries the id) and
        cache it for the process, since it never changes for a given token.
        """
        global _RESOLVED_USER_ID
        if self.user_id:
            return self.user_id
        if _RESOLVED_USER_ID is not None:
            return _RESOLVED_USER_ID
        info = await self.ping()
        _RESOLVED_USER_ID = info.get("_id")
        return _RESOLVED_USER_ID

    async def events(self, *, limit: int = 100) -> list[RelayEvent]:
        """Recent events, newest last. Used to catch up after the listener restarts."""
        async with self.connect() as ws:
            await ws.send(json.dumps({"action": "events", "limit": limit}))
            for _ in range(20):
                msg = json.loads(await ws.recv())
                if msg.get("action") == "events":
                    return [RelayEvent.from_message(e) for e in msg.get("events", [])]
        return []

    async def stream(self) -> AsyncIterator[RelayEvent]:
        """Every event the relay pushes, for as long as the connection holds.

        The caller is expected to be a single dedicated process. Running this on each API
        instance would hand every event to every instance, and each would act on it.
        """
        async with self.connect() as ws:
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("action") in ("agentlog", "relaylog", "event"):
                    yield RelayEvent.from_message(msg)
