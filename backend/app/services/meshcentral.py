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

import asyncio
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

#: The rights a per-org remote-support account gets on ITS device group and nothing else:
#: remote desktop control, with the terminal, files and Intel AMT tabs explicitly denied.
#: The viewer is desktop-only (hide=31) and the account exists solely to be logged into as,
#: so it is scoped as tightly as the feature allows.
#:
#: These are the real MeshCentral MESHRIGHT_* mesh-rights bits: REMOTECONTROL 8 (the only
#: GRANT here), NOTERMINAL 512, NOFILES 1024, NOAMT 2048 (denials). Everything not granted is
#: already denied, so no separate "registry"/"software" bit is needed — and MeshCentral has
#: none: mesh rights top out at RELAY 0x200000, so any higher bit is undefined. We deliberately
#: never set MANAGEUSERS 2, MANAGECOMPUTERS 4, AGENTCONSOLE 16 or REMOTECOMMAND 131072, which is
#: what keeps this account from pivoting to other groups or running commands. Setting undefined
#: bits was worse than useless: it protected nothing and could silently mean "grant" if a future
#: relay build assigned that bit — so the mask is exactly the four rights above.
REMOTE_CONTROL_MESH_RIGHTS = 8 | 512 | 1024 | 2048


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

        `gotonode` takes the BARE node id, with any "node//" prefix stripped — MeshCentral's
        own desktop links build it from `_id.split('/')[2]`, i.e. the part after "node//".
        Pass the prefixed form and the web app cannot resolve the node: it logs in fine but
        the desktop never connects, the iframe just blinks, and no consent prompt is ever
        raised on the device. The stored id keeps its prefix everywhere else; this endpoint,
        like /meshagents, is the exception.
        """
        self._require()
        cookie = self.encode_login_cookie(user_id)
        base = (self.url or "").rstrip("/")
        bare_node = node_id.removeprefix("node//")
        return (
            f"{base}/?login={quote(cookie, safe='')}"
            f"&gotonode={quote(bare_node, safe='')}&viewmode=11&hide=31"
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

    async def _await_result(self, ws: Any, payload: dict[str, Any], action: str) -> dict[str, Any]:
        """Send one control-channel command and read back its matching reply.

        Unlike the event stream, these admin commands DO echo their `action` (and the
        `responseid` we set), so a reply can be matched to its command — verified against the
        live relay. Everything else on the socket is skipped until that reply arrives.
        """
        await ws.send(json.dumps(payload))
        for _ in range(30):
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            if msg.get("action") == action:
                return msg
        raise MeshCentralError(f"The relay did not answer '{action}'.")

    async def provision_scoped_access(
        self, *, mesh_name: str, user_slug: str, password: str, rights: int
    ) -> tuple[str, str]:
        """Stand up one org's remote support on the relay, and return (mesh_id, user_id).

        The whole of enabling the feature for an organisation: one device group its machines
        enroll into, and one account — deliberately NOT a site admin — scoped to that group
        alone, which the viewer cookie names. That pairing is the cross-tenant boundary: the
        account can reach this org's group and no other. Done over the control channel in a
        single connection.

        The account password is random and never used — the browser logs in by a cookie ASTRA
        signs, never by password — so the account exists only to hold the group grant. Adding
        an account that already exists is treated as success, so a retry after a half-finished
        run completes rather than failing.

        When the account already existed, it is verified to be a NON site-admin before the group
        is granted to it: a viewer cookie names this account, and a cookie naming a site admin
        would see every org's devices regardless of any mesh grant. A freshly created account is
        a normal user by construction, so the check is only needed on the "already exists" path.
        """
        self._require()
        async with self.connect() as ws:
            mesh = await self._await_result(ws, {
                "action": "createmesh", "meshname": mesh_name, "meshtype": 2,
                "desc": "ASTRA remote support", "responseid": "astra"}, "createmesh")
            mesh_id = mesh.get("meshid")
            if not mesh_id:
                raise MeshCentralError(
                    f"The relay did not return a device group id ({mesh.get('result')}).")

            user = await self._await_result(ws, {
                "action": "adduser", "username": user_slug, "pass": password,
                "responseid": "astra"}, "adduser")
            result = str(user.get("result", "")).lower()
            if result not in ("ok", "") and "exist" not in result:
                raise MeshCentralError(f"The relay refused to create the account ({result}).")
            # Adopting a pre-existing account — refuse to bind a viewer cookie to it unless it is
            # a plain user. `siteadmin` is a bitmask; 0/None is a non-admin. A freshly created
            # account is a normal user by construction, so this only runs on the "exists" path.
            if "exist" in result and await self._user_siteadmin(ws, "user//" + user_slug):
                raise MeshCentralError(
                    "An account with this name already exists on the relay and is a site "
                    "administrator — refusing to scope remote support to it.")

            grant = await self._await_result(ws, {
                "action": "addmeshuser", "meshid": mesh_id, "usernames": [user_slug],
                "meshadmin": rights, "responseid": "astra"}, "addmeshuser")
            if not grant.get("success"):
                raise MeshCentralError(
                    f"The relay refused to grant group rights ({grant.get('result')}).")

            return mesh_id, "user//" + user_slug

    async def _user_siteadmin(self, ws: Any, user_id: str) -> int:
        """The `siteadmin` bitmask of one relay account, or 0 if it can't be found.

        Used to refuse binding a viewer cookie to a pre-existing site-admin account. The
        `users` reply carries the account list as either a list of records or a dict keyed by
        id, depending on relay version — both are handled.
        """
        reply = await self._await_result(ws, {"action": "users", "responseid": "astra"}, "users")
        users = reply.get("users", [])
        records = users.values() if isinstance(users, dict) else users
        for record in records:
            if isinstance(record, dict) and record.get("_id") == user_id:
                return int(record.get("siteadmin") or 0)
        return 0

    async def set_user_realname(self, *, user_id: str, realname: str) -> None:
        """Set a relay account's display name — the `{0}` the endpoint's consent prompt shows.

        ASTRA calls this just before a session so the person being asked sees WHO wants in and
        WHY, on their own screen, in the relay's own dialog (see infra/relay/apply_consent_branding.py).
        The relay updates the in-memory user and the next desktop connect reads the new name;
        the relay caps realname at 256 characters, so this does too.

        Uses the control-channel token, which is the site admin — editing another account needs
        the manage-users right, which the scoped per-org accounts deliberately do NOT have, so
        this cannot run as one of them. It is fire-and-forget: the caller treats a failure as
        "the prompt shows the account's standing name" rather than a reason to fail the request.
        The brief read after sending is only to let the relay process the edit before the socket
        closes; the reply is not needed.
        """
        self._require()
        async with self.connect() as ws:
            await ws.send(json.dumps(
                {"action": "edituser", "userid": user_id, "realname": realname[:256]}))
            try:
                await asyncio.wait_for(ws.recv(), timeout=5.0)
            except Exception:
                pass

    # There is deliberately no resolve_user_id() that hands back "whoever the control-channel
    # token belongs to". That user is the site-admin astraadmin, and minting a viewer cookie
    # in its name would log the browser in as an admin who can reach every org's device by
    # editing the node id in the URL. The user a viewer cookie names is always the requesting
    # device's own org — Organization.meshcentral_user_id, a per-org account scoped on the
    # relay to that org's device group alone. That is the whole of the cross-tenant boundary,
    # so the id has to come from the org row, never from the token or from config.

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
