#!/usr/bin/env python
"""Connect the ASTRA company page.

LinkedIn's authorisation is three-legged: a human signs in, LinkedIn hands back a code,
and the code is exchanged for a token. That token belongs to the person who signed in and
carries their admin rights over the page — so two things follow, and both matter more than
the mechanics:

* **The token expires after 60 days.** Programmatic refresh is available only to approved
  Marketing Developer Platform partners. Without that approval, somebody re-runs this
  flow in a browser roughly every two months. Plan for it; it will not announce itself,
  it will just start returning 401.
* **It is a credential for a real person's LinkedIn access.** This script never prints it
  and never asks you to paste it anywhere it could be read later. It writes to .env and
  tells you the one gcloud command that puts it in Secret Manager.

Usage:
    python scripts/setup_linkedin.py --auth-url
    python scripts/setup_linkedin.py --exchange <code>
    python scripts/setup_linkedin.py --organizations
    python scripts/setup_linkedin.py --check

Needs ASTRA_MKT_LINKEDIN_CLIENT_ID and ASTRA_MKT_LINKEDIN_CLIENT_SECRET in .env for the
first two; the rest use the token it stores.
"""
import argparse
import pathlib
import sys
import urllib.parse

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402

settings = get_settings()

AUTH = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN = "https://www.linkedin.com/oauth/v2/accessToken"
API = "https://api.linkedin.com/rest"

#: Write requires w_organization_social. r_organization_social is requested too so
#: --organizations can tell you which pages this token may actually post as, rather than
#: leaving you to find the numeric id by hand.
SCOPES = "w_organization_social r_organization_social"

#: LinkedIn requires a redirect URI registered on the app. Nothing listens here — you copy
#: the `code` parameter out of the browser's address bar after being redirected.
REDIRECT = "https://technomateai.com/linkedin-callback"

ENV_FILE = pathlib.Path(__file__).resolve().parent.parent / ".env"


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": settings.linkedin_api_version,
    }


def auth_url() -> int:
    client_id = settings.linkedin_client_id
    if not client_id:
        print("Set ASTRA_MKT_LINKEDIN_CLIENT_ID in .env first (LinkedIn app -> Auth tab).")
        return 1

    query = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT,
        "scope": SCOPES,
        # Not security here — nothing validates it, because nothing is listening on the
        # redirect. It is a marker so you can tell your own redirect from a stray one.
        "state": "astra-marketing",
    })
    print("1. Open this, signed in as an ADMIN of the ASTRA company page:\n")
    print(f"   {AUTH}?{query}\n")
    print("2. Approve. The browser lands on a page that does not exist — that is expected.")
    print("3. Copy the `code=` value out of the address bar (it expires in ~30 seconds).")
    print("4. Run: python scripts/setup_linkedin.py --exchange <code>")
    return 0


def exchange(code: str) -> int:
    client_id = settings.linkedin_client_id
    client_secret = settings.linkedin_client_secret
    if not (client_id and client_secret):
        print("Set ASTRA_MKT_LINKEDIN_CLIENT_ID and ..._CLIENT_SECRET in .env first.")
        return 1

    response = httpx.post(TOKEN, data={
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT,
    }, timeout=30.0)

    if response.status_code != 200:
        print(f"FAILED: LinkedIn refused the code ({response.status_code})")
        print(f"  {response.text[:400]}")
        print("\n  A code is single-use and expires in about 30 seconds. If it aged out,")
        print("  run --auth-url again and be quicker.")
        return 1

    data = response.json()
    token = data.get("access_token", "")
    if not token:
        print(f"FAILED: no access_token in the response: {str(data)[:300]}")
        return 1

    days = int(data.get("expires_in", 0)) // 86400
    _store("ASTRA_MKT_LINKEDIN_ACCESS_TOKEN", token)

    print(f"OK: token stored in .env. It is valid for {days} days.")
    print("\nPut it in Secret Manager without it passing through your shell history:\n")
    print("  grep '^ASTRA_MKT_LINKEDIN_ACCESS_TOKEN=' .env | cut -d= -f2- | tr -d '\\r\\n' \\")
    print("    | gcloud secrets create ASTRA_MKT_LINKEDIN_ACCESS_TOKEN --data-file=-\n")
    print("Then: python scripts/setup_linkedin.py --organizations")
    return 0


def organizations() -> int:
    """Which pages can this token post as, and what is each one's numeric id?"""
    token = _token()
    if not token:
        return 1

    response = httpx.get(
        f"{API}/organizationAcls",
        params={"q": "roleAssignee", "role": "ADMINISTRATOR", "state": "APPROVED"},
        headers=_headers(token), timeout=30.0,
    )
    if response.status_code != 200:
        print(f"FAILED: {response.status_code} {response.text[:400]}")
        print("\n  403 here usually means the app has not been granted the Community")
        print("  Management API product, which is a separate request in the LinkedIn")
        print("  developer console and is not automatic.")
        return 1

    elements = response.json().get("elements", [])
    if not elements:
        print("This token administers no pages. Sign in as a page ADMINISTRATOR and retry.")
        return 1

    print("Pages this token can post as:\n")
    for element in elements:
        urn = element.get("organization", "")
        org_id = urn.rsplit(":", 1)[-1]
        print(f"  {org_id}   ({urn})")
    print("\nPut the right id in .env as ASTRA_MKT_LINKEDIN_ORGANIZATION_ID,")
    print("and in Secret Manager as ASTRA_MKT_LINKEDIN_ORGANIZATION_ID.")
    return 0


def check() -> int:
    """Is this thing going to work, without posting anything to find out."""
    token = _token()
    if not token:
        return 1
    if not settings.linkedin_organization_id:
        print("ASTRA_MKT_LINKEDIN_ORGANIZATION_ID is not set — run --organizations.")
        return 1

    urn = f"urn:li:organization:{settings.linkedin_organization_id}"
    response = httpx.get(
        f"{API}/posts",
        params={"q": "author", "author": urn, "count": 1},
        headers={**_headers(token), "X-RestLi-Method": "FINDER"}, timeout=30.0,
    )

    if response.status_code == 401:
        print("FAILED: the token is rejected. These last 60 days — re-run --auth-url.")
        return 1
    if response.status_code == 403:
        print("FAILED: the token cannot act for this page. Either the scope")
        print("  w_organization_social was not granted, or whoever authorised it is no")
        print("  longer an admin of the page.")
        return 1
    if response.status_code >= 400:
        print(f"FAILED: {response.status_code} {response.text[:400]}")
        return 1

    print(f"OK: the token can read and post as {urn}.")
    print(f"  API version in use: {settings.linkedin_api_version}")
    print("\nNothing was posted. To see what a draft would look like on the wire:")
    print("  GET /api/v1/content/{id}/preview")
    return 0


def _token() -> str:
    token = settings.linkedin_access_token
    if not token:
        print("ASTRA_MKT_LINKEDIN_ACCESS_TOKEN is not set — run --auth-url first.")
    return token


def _store(name: str, value: str) -> None:
    """Write to .env, replacing any existing line for the same key.

    Appending blindly would leave two lines for one key, and which one wins depends on
    the parser — a way to spend an afternoon on a token that was already correct.
    """
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    kept = [ln for ln in lines if not ln.startswith(f"{name}=")]
    kept.append(f"{name}={value}")
    ENV_FILE.write_text("\n".join(kept) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--auth-url", action="store_true", help="Print the sign-in URL")
    group.add_argument("--exchange", metavar="CODE", help="Trade the code for a token")
    group.add_argument("--organizations", action="store_true", help="List page ids")
    group.add_argument("--check", action="store_true", help="Verify without posting")
    args = parser.parse_args()

    if args.auth_url:
        return auth_url()
    if args.exchange:
        return exchange(args.exchange)
    if args.organizations:
        return organizations()
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
