"""Why a 401 happened, and who gets told.

Written after an n8n Header Auth credential was set to the bare admin token instead of
`Bearer <token>`. Every scheduled sweep 401'd for hours; the header was present, the token
in it was correct, and the server said only "Not authorised" — so there was nothing to go
on. These tests pin the split that fixes that: the log names the mistake, the response
still says nothing.
"""
import pytest

from app.core.config import get_settings


async def _get(client, headers=None):
    return await client.get("/api/v1/leads?limit=1", headers=headers or {})


# ── The caller learns nothing ─────────────────────────────────────────────────

@pytest.mark.parametrize("headers", [
    {},
    {"Authorization": "wrong-scheme-entirely"},
    {"Authorization": "Bearer not-the-token"},
    {"Authorization": "Basic dXNlcjpwYXNz"},
    {"Authorization": "Bearer "},
])
async def test_every_refusal_looks_identical_from_outside(client, headers):
    """A caller probing this endpoint must not be able to tell which mistake they made —
    that is a map towards the right one."""
    response = await _get(client, headers)

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authorised."
    assert response.headers["www-authenticate"] == "Bearer"


async def test_the_right_token_still_works(client, admin_token):
    response = await _get(client, {"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200


# ── The log learns everything ─────────────────────────────────────────────────

async def test_a_missing_header_says_so(client, caplog):
    with caplog.at_level("WARNING", logger="astra.mkt.deps"):
        await _get(client)
    assert "no Authorization header" in caplog.text


async def test_the_bare_token_mistake_is_named(client, admin_token, caplog):
    """The exact n8n misconfiguration: the token, correct, without the scheme.

    This is the message that would have turned an afternoon into a minute.
    """
    with caplog.at_level("WARNING", logger="astra.mkt.deps"):
        await _get(client, {"Authorization": admin_token})

    assert "no scheme prefix" in caplog.text
    assert "'Bearer <token>'" in caplog.text


async def test_a_wrong_length_token_is_distinguished_from_a_wrong_one(client, caplog):
    with caplog.at_level("WARNING", logger="astra.mkt.deps"):
        await _get(client, {"Authorization": "Bearer short"})
    assert "characters; this service expects" in caplog.text


async def test_a_right_length_wrong_value_token_says_exactly_that(client, admin_token,
                                                                  caplog):
    with caplog.at_level("WARNING", logger="astra.mkt.deps"):
        await _get(client, {"Authorization": "Bearer " + "x" * len(admin_token)})
    assert "right length but does not match" in caplog.text


async def test_the_presented_credential_is_never_logged(client, caplog):
    """A guess at a secret is still a secret. Writing guesses into logs is how one ends up
    somewhere it was never stored.

    This test found the bug it was written to prevent: the first version reported
    `authorization.split(" ")[0]` as "the scheme", which is the entire header when it
    contains no space — the bare-token case, which is the one this diagnosis exists for.
    """
    guess = "supersecretguess1234567890"

    with caplog.at_level("WARNING", logger="astra.mkt.deps"):
        await _get(client, {"Authorization": f"Bearer {guess}"})
        await _get(client, {"Authorization": guess})

    assert guess not in caplog.text


async def test_the_real_token_is_never_logged(client, admin_token, caplog):
    with caplog.at_level("WARNING", logger="astra.mkt.deps"):
        await _get(client, {"Authorization": admin_token})
    assert admin_token not in caplog.text


# ── Unconfigured is shut, not open ────────────────────────────────────────────

async def test_no_configured_token_closes_the_door(client, monkeypatch):
    """503, not 200. A missing credential must never be the thing that produces a public
    list of every prospect the company has."""
    monkeypatch.setattr(get_settings(), "admin_token", "")

    response = await _get(client, {"Authorization": "Bearer anything"})

    assert response.status_code == 503
    assert "not configured" in response.json()["detail"].lower()
