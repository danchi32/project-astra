"""Relays the signed agent-update manifest to enrolled devices.

The backend is deliberately NOT a signing authority. It fetches the manifest and its
signature (produced offline / in CI with a key this server never holds) from configured
URLs, caches them briefly, and hands them to agents. Agents verify the signature against a
public key pinned in their binary, so a compromise of this backend cannot forge an update —
the worst it could do is withhold or replay an already-signed, still-valid manifest.
"""
from __future__ import annotations

import time

import httpx

from app.core.config import Settings

# Process-wide cache so a fleet heartbeat storm doesn't hammer the upstream (e.g. GitHub).
_cache: dict[str, tuple[float, str, str]] = {}


class AgentUpdateService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def configured(self) -> bool:
        m = self._settings.agent_update_manifest_url
        s = self._settings.agent_update_signature_url
        # Both must be set AND https — never fetch the channel over an unencrypted/other scheme.
        return bool(
            m and s
            and m.lower().startswith("https://")
            and s.lower().startswith("https://")
        )

    async def current(self) -> tuple[str, str] | None:
        """Return (manifest_json, signature_b64) for the latest release, or None when the
        channel isn't configured or the upstream can't be reached."""
        if not self.configured:
            return None

        manifest_url = self._settings.agent_update_manifest_url or ""
        cache_key = manifest_url
        ttl = max(0, self._settings.agent_update_cache_seconds)
        now = time.monotonic()

        max_stale = max(0, self._settings.agent_update_max_stale_seconds)

        cached = _cache.get(cache_key)
        if cached is not None and now - cached[0] < ttl:
            return cached[1], cached[2]

        def _stale():
            # Only fall back to a cached manifest while it's within the max-stale window, so a
            # prolonged upstream outage stops serving an old manifest rather than pinning it.
            if cached is not None and now - cached[0] < max_stale:
                return cached[1], cached[2]
            return None

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                manifest_resp = await client.get(manifest_url)
                signature_resp = await client.get(
                    self._settings.agent_update_signature_url or ""
                )
        except httpx.HTTPError:
            return _stale()

        if manifest_resp.status_code != 200 or signature_resp.status_code != 200:
            return _stale()

        manifest = manifest_resp.text
        signature = signature_resp.text.strip()
        _cache[cache_key] = (now, manifest, signature)
        return manifest, signature
