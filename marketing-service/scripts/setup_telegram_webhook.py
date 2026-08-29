#!/usr/bin/env python
"""Point Telegram at the approval desk.

Telegram does not poll us and we do not poll Telegram: the bot is told once, out of band,
where to deliver updates. That registration is global to the bot token — there is exactly
one webhook URL per bot — which has two consequences worth stating before you run this:

* **Running this against staging takes production's desk offline.** The same bot cannot
  serve both. Use a separate bot for staging, or accept that whichever ran last wins.
* **The secret is set here and read by the service.** They must match. If you rotate one,
  rotate both, in that order — a service expecting a new secret while Telegram still sends
  the old one refuses every update, which looks exactly like the bot being broken.

Usage:
    python scripts/setup_telegram_webhook.py --url https://<service>/api/v1/telegram/webhook
    python scripts/setup_telegram_webhook.py --status
    python scripts/setup_telegram_webhook.py --delete

Reads ASTRA_MKT_TELEGRAM_BOT_TOKEN and ASTRA_MKT_TELEGRAM_WEBHOOK_SECRET from the
environment or .env, exactly as the service does.
"""
import argparse
import asyncio
import secrets
import sys

import httpx

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402

settings = get_settings()
API = "https://api.telegram.org"

#: Everything else Telegram could send — channel posts, edited messages, poll answers,
#: chat member changes — is surface we do not read. Naming the two we handle means the
#: rest never reaches the endpoint at all.
ALLOWED_UPDATES = ["message", "callback_query"]


async def call(method: str, payload: dict | None = None) -> dict:
    url = f"{API}/bot{settings.telegram_bot_token}/{method}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, json=payload or {})
    try:
        return response.json()
    except ValueError:
        return {"ok": False, "description": response.text[:400]}


def _require_token() -> None:
    if not settings.telegram_bot_token:
        sys.exit("ASTRA_MKT_TELEGRAM_BOT_TOKEN is not set.")


async def set_webhook(url: str) -> int:
    _require_token()
    if not settings.telegram_webhook_secret:
        print("ASTRA_MKT_TELEGRAM_WEBHOOK_SECRET is not set.\n")
        print("The service refuses every update without it, so registering the webhook")
        print("now would leave a desk that silently never responds. Set this first:\n")
        print(f"  ASTRA_MKT_TELEGRAM_WEBHOOK_SECRET={secrets.token_urlsafe(32)}\n")
        print("Store it in Secret Manager as ASTRA_MKT_TELEGRAM_WEBHOOK_SECRET, put the")
        print("same value in your local .env, redeploy, then run this again.")
        return 1

    if not url.startswith("https://"):
        sys.exit("Telegram only delivers to https. Refusing to register an http URL.")

    result = await call("setWebhook", {
        "url": url,
        "secret_token": settings.telegram_webhook_secret,
        "allowed_updates": ALLOWED_UPDATES,
        # Anything queued from before this registration is from a different deployment or
        # a different secret. Delivering it now would replay stale decisions.
        "drop_pending_updates": True,
    })

    if not result.get("ok"):
        print(f"FAILED: Telegram refused: {result.get('description')}")
        return 1

    print(f"OK: Webhook registered: {url}")
    print(f"  Updates delivered: {', '.join(ALLOWED_UPDATES)}")
    print("  Secret token: set (the service compares it in constant time)")
    return 0


async def status() -> int:
    _require_token()
    info = (await call("getWebhookInfo")).get("result", {})
    if not info.get("url"):
        print("No webhook registered — the desk receives nothing.")
        return 1

    print(f"URL: {info['url']}")
    # Deliberately not reported: getWebhookInfo does not return the secret token or
    # whether one is set. The only observable evidence is `last_error_message` below —
    # a 401 there is what a mismatched secret looks like from the outside.
    print(f"Allowed updates: {info.get('allowed_updates') or 'all (too many — re-run --url)'}")
    print(f"Pending updates: {info.get('pending_update_count', 0)}")

    # The two fields that actually diagnose a broken desk. Telegram keeps retrying and
    # reports the last failure here, which is the only place the reason is visible.
    if info.get("last_error_message"):
        print(f"\nWARNING: Last delivery error: {info['last_error_message']}")
        print("  A 401 here almost always means the secret in Secret Manager and the one")
        print("  registered with Telegram have drifted apart. Re-run with --url to reset.")
        return 1
    print("\nNo delivery errors reported.")
    return 0


async def delete() -> int:
    _require_token()
    result = await call("deleteWebhook", {"drop_pending_updates": True})
    print("OK: Webhook removed." if result.get("ok") else f"FAILED: {result.get('description')}")
    return 0 if result.get("ok") else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="Public https URL of /api/v1/telegram/webhook")
    group.add_argument("--status", action="store_true", help="What Telegram thinks is registered")
    group.add_argument("--delete", action="store_true", help="Stop delivery entirely")
    args = parser.parse_args()

    if args.status:
        return asyncio.run(status())
    if args.delete:
        return asyncio.run(delete())
    return asyncio.run(set_webhook(args.url))


if __name__ == "__main__":
    raise SystemExit(main())
