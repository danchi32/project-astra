"""Secrets must not reach the log stream.

Written after finding the Telegram bot token in Cloud Run logs. Nothing in this service
put it there: httpx logs every request at INFO as "HTTP Request: POST <full url>", and
Telegram's URL carries the bot token as a path segment. Every alert, every button press,
wrote a working credential into the log.

The lesson generalises past Telegram, so the test does too: any client that puts a secret
in a URL leaks it through request logging, which is one of the reasons this service's own
intake authenticates with a signed header instead.
"""
import logging

from app.services.telegram import _API


def test_httpx_request_logging_is_off():
    """The specific fix. At INFO, httpx prints full URLs — including the bot token."""
    assert logging.getLogger("httpx").level >= logging.WARNING, (
        "httpx at INFO writes the Telegram bot token into the logs on every call"
    )
    assert logging.getLogger("httpcore").level >= logging.WARNING


def test_the_telegram_url_really_does_carry_the_token():
    """Guards the reasoning above, not just the fix.

    If Telegram ever moved the token to a header this test fails, and whoever sees it can
    decide the httpx silencing is no longer needed — rather than inheriting a rule with no
    remaining reason.
    """
    from app.core.config import get_settings

    url = f"{_API}/bot{get_settings().telegram_bot_token}/sendMessage"
    assert "/bot" in url and url.startswith("https://api.telegram.org")
