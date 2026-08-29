"""The drafting agent.

No test here calls Anthropic — the suite empties every credential before importing the
app, and an autouse guard fails the run if any integration is live. What is tested is
everything around the model call: the contract it is handed, the correction it is given
when the checker refuses it, and the ceiling on how long it may keep trying.

The model call itself is exercised against a fake, because the interesting failures are
not "does the SDK work" but "what does the agent do when the answer comes back wrong".
"""
import pytest

from app.models.content import ContentChannel
from app.services.claims import brand_bible_prompt
from app.services.drafting import MAX_ATTEMPTS, Draft, DraftingAgent, channel_brief
from app.services.exceptions import NotConfiguredError

GOOD = Draft(
    body="ASTRA gathers endpoint evidence before it proposes a fix. Every remediation is "
         "tiered, and the tier is enforced server-side rather than in a prompt.",
    hashtags="#WindowsEndpointManagement #ITOperations",
    cta="Book an Endpoint Automation Assessment",
    rationale="Leads with the mechanism, which is what this reader trusts.",
)
BAD = Draft(
    body="Certificate-based enrollment for every agent, with fully autonomous remediation "
         "across Windows, macOS and Linux.",
    cta="Book an Endpoint Automation Assessment",
    rationale="Punchier.",
)


class FakeModel:
    """Returns a scripted sequence of drafts and records what it was asked."""

    def __init__(self, *drafts: Draft) -> None:
        self.drafts = list(drafts)
        self.prompts: list[str] = []

    async def __call__(self, instruction: str, correction: str | None) -> Draft:
        self.prompts.append(instruction if correction is None
                            else f"{instruction}\n\n{correction}")
        return self.drafts[min(len(self.prompts), len(self.drafts)) - 1]


@pytest.fixture
def agent(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-test-not-used")
    return DraftingAgent()


# ── Inert without a key ───────────────────────────────────────────────────────

async def test_drafting_is_unavailable_without_a_key():
    """The service still runs. Drafting simply is not offered."""
    assert DraftingAgent().enabled is False

    with pytest.raises(NotConfiguredError, match="ANTHROPIC"):
        await DraftingAgent().draft(channel=ContentChannel.LINKEDIN, brief="anything")


# ── The channel contract ──────────────────────────────────────────────────────

def test_channel_brief_comes_from_voice_yaml():
    """Stated once, in the file a person edits — not in a prompt string nobody opens."""
    linkedin = channel_brief(ContentChannel.LINKEDIN)

    assert "120-200 words" in linkedin
    assert "#WindowsEndpointManagement" in linkedin
    # The link-placement rule is real and non-obvious; a draft that ignores it loses reach.
    assert "first comment" in linkedin


def test_x_brief_carries_the_cost_of_a_link():
    """$0.20 a post with a link against $0.015 without. The model should know."""
    assert "$0.20" in channel_brief(ContentChannel.X)


def test_an_unknown_channel_still_produces_a_brief():
    assert "google_business_profile" in channel_brief(ContentChannel.GBP)


# ── The system prompt ─────────────────────────────────────────────────────────

def test_the_model_is_handed_the_whole_contract():
    prompt = brand_bible_prompt()

    assert "NEVER CLAIM" in prompt          # what is false
    assert "WHO IS READING" in prompt       # who it is for
    assert "HOW TO WRITE" in prompt         # how it should sound
    assert "restart_explorer" in prompt     # the real actions, so it invents none


# ── The self-correction loop ──────────────────────────────────────────────────

async def test_a_clean_draft_takes_one_attempt(agent, monkeypatch):
    fake = FakeModel(GOOD)
    monkeypatch.setattr(agent, "_generate", fake)

    result = await agent.draft(channel=ContentChannel.LINKEDIN, brief="Explain the tiers.")

    assert result.attempts == 1
    assert not result.blocked
    assert len(fake.prompts) == 1


async def test_a_blocked_draft_is_told_what_it_got_wrong_and_tries_again(agent, monkeypatch):
    fake = FakeModel(BAD, GOOD)
    monkeypatch.setattr(agent, "_generate", fake)

    result = await agent.draft(channel=ContentChannel.LINKEDIN, brief="Explain the tiers.")

    assert result.attempts == 2
    assert not result.blocked

    correction = fake.prompts[1]
    assert "Certificate-based" in correction, "the model must be shown its own words"
    assert "token-based" in correction.lower(), (
        "naming the error is not enough — a model told only to stop saying something "
        "reaches for a synonym"
    )
    assert "synonym" in correction


async def test_it_gives_up_rather_than_looping(agent, monkeypatch):
    """A model that cannot avoid a forbidden claim twice will not manage it in five, and
    the founder should see that rather than a retry bill."""
    fake = FakeModel(BAD, BAD, BAD, BAD)
    monkeypatch.setattr(agent, "_generate", fake)

    result = await agent.draft(channel=ContentChannel.LINKEDIN, brief="Explain the tiers.")

    assert result.attempts == MAX_ATTEMPTS
    assert result.blocked
    assert len(fake.prompts) == MAX_ATTEMPTS
    assert result.findings, "a blocked result must say what was wrong with it"


async def test_a_blocked_draft_is_still_returned(agent, monkeypatch):
    """Kept, not discarded. A blocked version is evidence about the prompt, and throwing
    it away hides a pattern worth seeing."""
    monkeypatch.setattr(agent, "_generate", FakeModel(BAD, BAD))

    result = await agent.draft(channel=ContentChannel.LINKEDIN, brief="x")

    assert result.draft is not None
    assert result.draft.body


# ── Revision ──────────────────────────────────────────────────────────────────

async def test_human_feedback_goes_in_verbatim(agent, monkeypatch):
    """Paraphrasing feedback before acting on it is how a revision answers a note nobody
    wrote."""
    fake = FakeModel(GOOD)
    monkeypatch.setattr(agent, "_generate", fake)

    await agent.revise(
        channel=ContentChannel.LINKEDIN,
        previous="the old post",
        feedback="Make this more professional and focus more on the ROI.",
    )

    prompt = fake.prompts[0]
    assert "Make this more professional and focus more on the ROI." in prompt
    assert "<feedback>" in prompt, "untrusted text is quoted, not merged into instructions"
    assert "leave the rest alone" in prompt
