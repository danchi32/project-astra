"""Thin client over Resend's Domains API — the machinery behind the DNS-verified
sending model. ASTRA registers each customer's domain under its own single Resend
account, hands the org the DNS records to add, and verifies them. One API key
(ASTRA's) serves every tenant; orgs never see or hold a key.

Docs: https://resend.com/docs/api-reference/domains
"""
from __future__ import annotations

import httpx

from app.core.config import get_settings

_BASE = "https://api.resend.com/domains"


class EmailProviderError(RuntimeError):
    """A Resend API call failed (or the provider isn't configured)."""


def provider_configured() -> bool:
    return bool(get_settings().resend_api_key)


def _headers() -> dict[str, str]:
    key = get_settings().resend_api_key
    if not key:
        raise EmailProviderError(
            "Email provider is not configured on this deployment (ASTRA_RESEND_API_KEY). "
            "Set it before organizations can verify a sending domain."
        )
    return {"Authorization": f"Bearer {key}"}


async def create_domain(name: str) -> dict:
    """Register a domain and get back its id + the DNS records to publish."""
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(_BASE, headers=_headers(), json={"name": name})
    return _json_or_raise(resp, f"create domain {name}")


async def get_domain(domain_id: str) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{_BASE}/{domain_id}", headers=_headers())
    return _json_or_raise(resp, "get domain")


async def verify_domain(domain_id: str) -> dict:
    """Ask Resend to (re)check the DNS records now."""
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(f"{_BASE}/{domain_id}/verify", headers=_headers())
    return _json_or_raise(resp, "verify domain")


def _json_or_raise(resp: httpx.Response, what: str) -> dict:
    if resp.status_code >= 400:
        raise EmailProviderError(f"Resend {what} failed ({resp.status_code}): {resp.text[:300]}")
    try:
        return resp.json()
    except ValueError:
        raise EmailProviderError(f"Resend {what} returned a non-JSON response.")


def normalize_records(payload: dict) -> list[dict]:
    """Flatten Resend's DNS records into the shape the portal shows the org."""
    records = payload.get("records") or []
    out: list[dict] = []
    for r in records:
        out.append({
            "type": r.get("type", ""),
            "name": r.get("name", ""),
            "value": r.get("value", ""),
            "ttl": str(r.get("ttl", "Auto")),
            "priority": r.get("priority"),
            "purpose": r.get("record", ""),   # e.g. "DKIM", "SPF"
            "status": r.get("status", ""),
        })
    return out
