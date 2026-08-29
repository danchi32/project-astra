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


# ── The fleet mockup ──────────────────────────────────────────────────────────

VISUALS_TSX = WEBSITE / "src" / "components" / "visuals.tsx"

#: Figures that were once printed inside the product mockup as if measured. None was.
#: They are listed by value because that is what a reader sees; if any returns, it will
#: return as one of these.
INVENTED_FLEET_FIGURES = ('"248"', '"1,204"', '"38s"', '"99.9%"', '"−72% vs manual"')


@pytest.fixture(scope="module")
def visuals() -> str:
    if not VISUALS_TSX.exists():
        pytest.skip(f"{VISUALS_TSX} not present")
    return VISUALS_TSX.read_text(encoding="utf-8")


def test_the_fleet_mockup_states_no_invented_figures(visuals: str) -> None:
    """The panel is titled with the live product domain, which is what makes this matter.

    Sample data in a product mockup is ordinary. Sample data in a panel captioned
    `astra.technomateai.com — Fleet Dashboard` reads as a screenshot of a running system,
    and once the homepage began reporting real counts from the database the two were
    making contradictory claims about the same fleet.
    """
    found = [f for f in INVENTED_FLEET_FIGURES if f in visuals]
    assert not found, (
        f"{VISUALS_TSX.name} prints {found} inside the fleet dashboard. Those numbers "
        "were never measured, and the panel is captioned with the real product domain."
    )


def test_the_fleet_mockup_reads_its_figures_from_the_platform(visuals: str) -> None:
    """Banning the old literals is not enough — new ones can be typed.

    This asserts the shape instead: the figures come from the live endpoint, so there is
    nowhere to put an invented one.
    """
    assert "usePlatformStats" in visuals, (
        "the fleet dashboard no longer reads live stats; its figures are literals again"
    )


def test_an_unavailable_api_shows_a_dash_not_a_zero(visuals: str) -> None:
    """"0 devices managed" is a claim, and a false one. A dash is visibly an absence."""
    assert '"—"' in visuals, (
        "fleetFigure should fall back to an em dash; a zero would assert an empty fleet"
    )
