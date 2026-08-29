"""The image that goes out with a post.

One test here matters more than the rest: the sentence on the card goes through the claim
checker. A picture carrying a line reaches more people than the paragraph under it — a
scroller sees the graphic before any words — so copy that skipped the check would be
exempting exactly what most people actually read.

The rest cover the drawing itself, where the failure modes are quiet: a card that renders
blank, or crops its own sentence, still looks like a successful publish.
"""
import io

import pytest

from app.models.content import ContentChannel
from app.services.cards import SIZE, CardError, fallback_line, render
from app.services.content import ContentService
from app.services.exceptions import ValidationError

TRUE_LINE = "The tier is enforced on the server, not in the prompt."
FALSE_LINE = "Certificate-based enrollment, with fully autonomous fixes."


# ── The card is not a way around the gate ─────────────────────────────────────

@pytest.fixture
async def service(session_factory):
    async with session_factory() as session:
        yield ContentService(session)


async def test_a_false_claim_on_the_card_blocks_the_whole_draft(service):
    """The point of the whole file.

    The body is impeccable and the graphic is not. If `card_line` were left out of the
    check this would sail through, and the false claim would be the largest text in the
    post.
    """
    item = await service.create(
        channel=ContentChannel.LINKEDIN, actor="drafting-agent",
        body="ASTRA gathers endpoint evidence before it proposes a fix.",
        card_line=FALSE_LINE,
    )

    with pytest.raises(ValidationError):
        await service.submit_for_review(item.id, actor="drafting-agent")


async def test_the_card_line_is_stored_with_the_version(service):
    """It has to live on the version, not be re-derived, or the approval does not cover
    the words that were on screen."""
    item = await service.create(
        channel=ContentChannel.LINKEDIN, actor="agent",
        body="Evidence first.", card_line=TRUE_LINE,
    )
    stored = await service.get(item.id)
    assert stored.versions[0].card_line == TRUE_LINE


async def test_the_checkers_verdict_covers_the_card(service):
    item = await service.create(
        channel=ContentChannel.LINKEDIN, actor="agent",
        body="Evidence first.", card_line=FALSE_LINE,
    )
    stored = await service.get(item.id)
    assert stored.versions[0].check_result["blockers"], (
        "the stored verdict has to reflect the card copy, not just the body"
    )


# ── The drawing ───────────────────────────────────────────────────────────────

def _open(png: bytes):
    from PIL import Image

    return Image.open(io.BytesIO(png))


def test_it_renders_a_png_at_linkedins_ratio():
    image = _open(render(TRUE_LINE, eyebrow="Self-healing"))
    assert image.format == "PNG"
    assert image.size == SIZE == (1200, 627)


def test_an_empty_line_is_refused_rather_than_drawn_blank():
    """A card with no message still occupies the post. Refusing is louder than an empty
    graphic that looks like it worked."""
    for empty in ("", "   ", "\n"):
        with pytest.raises(CardError):
            render(empty)


def test_the_same_line_renders_the_same_bytes():
    """Rendering is pure, which is why the image is never stored: it can be regenerated
    whenever it is needed, and cannot drift from the words that were approved."""
    assert render(TRUE_LINE, eyebrow="Tiers") == render(TRUE_LINE, eyebrow="Tiers")


def test_a_different_line_renders_differently():
    assert render(TRUE_LINE) != render("Something else entirely.")


@pytest.mark.parametrize("line", [
    "Short.",
    TRUE_LINE,
    "Evidence before action, every single time, on every endpoint in the fleet, with "
    "the tier enforced server-side rather than suggested in a prompt somewhere.",
])
def test_lines_of_any_length_stay_inside_the_card(line):
    """Shrink, never crop. A sentence cut off on a graphic is the kind of mistake that
    gets screenshotted."""
    image = _open(render(line)).convert("L")

    # The bottom and right margins must hold no glyphs. Cropped text would bleed into them.
    width, height = image.size
    right = image.crop((width - 20, 0, width, height))
    bottom = image.crop((0, height - 20, width, height))
    assert max(right.getextrema()) < 120, "text reached the right edge"
    assert max(bottom.getextrema()) < 120, "text reached the bottom edge"


def test_the_card_is_not_blank():
    """A backdrop with no text on it renders fine and publishes fine, so nothing else
    would catch it."""
    image = _open(render(TRUE_LINE)).convert("L")
    low, high = image.getextrema()
    assert high > 200, "no light pixels — the text did not draw"
    assert high - low > 150, "no contrast — this is a flat rectangle"


# ── The compatibility shim ────────────────────────────────────────────────────

def test_older_versions_fall_back_to_their_opening_line():
    """Rows written before card_line existed still need a card."""
    body = "An automation tool that fixes everything is the one you stop trusting.\n\nMore."
    assert fallback_line(body).startswith("An automation tool")
    assert "\n" not in fallback_line(body)


def test_the_fallback_gives_up_rather_than_inventing():
    assert fallback_line("") == ""
    assert fallback_line("   \n  ") == ""


# ── Over HTTP ─────────────────────────────────────────────────────────────────

async def test_the_card_endpoint_returns_an_image(client, admin_token, session_factory):
    async with session_factory() as session:
        item = await ContentService(session).create(
            channel=ContentChannel.LINKEDIN, actor="agent",
            body="Evidence first.", card_line=TRUE_LINE, campaign="tiers",
        )

    response = await client.get(
        f"/api/v1/content/{item.id}/card.png",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert _open(response.content).size == SIZE


async def test_the_card_endpoint_needs_the_admin_token(client, session_factory):
    """Unpublished marketing copy, set large. Same door as everything else here."""
    async with session_factory() as session:
        item = await ContentService(session).create(
            channel=ContentChannel.LINKEDIN, actor="agent",
            body="Evidence first.", card_line=TRUE_LINE,
        )

    response = await client.get(f"/api/v1/content/{item.id}/card.png")
    assert response.status_code == 401


# ── The assets have to ship ───────────────────────────────────────────────────

def test_the_bundled_font_is_present():
    """python:3.11-slim ships no fonts at all, so this file is the only reason text
    renders in production. A stray *.ttf in .gitignore would break every card."""
    from app.services.cards import _FONT

    assert _FONT.exists(), f"the bundled font is missing at {_FONT}"
    assert _FONT.stat().st_size > 100_000, "font file looks truncated"


def test_a_missing_font_says_what_is_actually_wrong(monkeypatch):
    """Pillow says "cannot open resource", which sends the reader to look at Pillow."""
    from pathlib import Path

    import app.services.cards as cards
    monkeypatch.setattr(cards, "_FONT", Path("nowhere/Inter.ttf"))

    with pytest.raises(CardError, match="missing from the deployed image"):
        render(TRUE_LINE)


def test_the_card_still_draws_without_the_logo(monkeypatch):
    """A missing logo degrades; a missing font cannot. Different assets, different
    severity, and the code should not treat them the same."""
    from pathlib import Path

    import app.services.cards as cards
    monkeypatch.setattr(cards, "_LOGO", Path("nowhere/logo.png"))

    image = _open(render(TRUE_LINE))
    assert image.size == SIZE
