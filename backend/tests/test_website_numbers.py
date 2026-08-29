"""Numbers the website states about the product must match the product.

`claims.yaml` covers which actions may be described. This covers the counts printed
beside them — a different failure, and a quieter one. The About page said "23 Automated
remediation actions" while the registry held 29: not invented, just left behind, which is
how every stale number starts.

Two copies are checked because the site keeps each string twice — the JSON it loads at
runtime and the inline fallback the static export bakes in. Fixing one and not the other
leaves the page correct in the HTML and wrong once it hydrates.
"""
import json
import pathlib
import re

import pytest

from app.services.remediation.actions import _ACTIONS

WEBSITE = pathlib.Path(__file__).resolve().parents[2] / "website"
CONTENT_JSON = WEBSITE / "public" / "content.json"
ABOUT_TSX = WEBSITE / "src" / "app" / "about" / "AboutContent.tsx"


@pytest.fixture(scope="module")
def content() -> dict:
    if not CONTENT_JSON.exists():
        pytest.skip(f"{CONTENT_JSON} not present")
    return json.loads(CONTENT_JSON.read_text(encoding="utf-8"))


def test_content_json_states_the_real_action_count(content: dict) -> None:
    stats = content["about"]["stats"]
    stated = next(
        s["value"] for s in stats if "remediation action" in s["label"].lower()
    )
    assert int(stated) == len(_ACTIONS), (
        f"content.json says {stated} remediation actions; the registry has "
        f"{len(_ACTIONS)}. The page is describing an older product."
    )


def test_the_baked_in_fallback_says_the_same_thing() -> None:
    if not ABOUT_TSX.exists():
        pytest.skip(f"{ABOUT_TSX} not present")

    source = ABOUT_TSX.read_text(encoding="utf-8")
    match = re.search(
        r'\{\s*value:\s*"(\d+)",\s*label:\s*"[^"]*[Rr]emediation actions"', source
    )
    assert match, "could not find the action-count stat in AboutContent.tsx"
    assert int(match.group(1)) == len(_ACTIONS), (
        f"AboutContent.tsx bakes in {match.group(1)} but the registry has "
        f"{len(_ACTIONS)}. The static HTML would ship the wrong number even with "
        "content.json corrected."
    )


def test_the_two_copies_agree(content: dict) -> None:
    """They are rendered from the same slot, so a mismatch means one silently wins."""
    if not ABOUT_TSX.exists():
        pytest.skip(f"{ABOUT_TSX} not present")

    from_json = next(
        s["value"] for s in content["about"]["stats"]
        if "remediation action" in s["label"].lower()
    )
    match = re.search(
        r'\{\s*value:\s*"(\d+)",\s*label:\s*"[^"]*[Rr]emediation actions"',
        ABOUT_TSX.read_text(encoding="utf-8"),
    )
    assert match and match.group(1) == str(from_json)
