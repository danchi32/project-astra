"""voice.yaml and icp.yaml, and the places they must agree with running code.

claims.yaml is answerable to the remediation registry. These two are answerable to the
lead scorer and to the copy a person already wrote — because a brand file that drifts from
the system it describes is worse than no brand file: every draft inherits it, and nothing
downstream catches it, since the checker reads the draft rather than the instructions.
"""
import pytest

from app.services.claims import brand_bible_prompt, check_text, load_icp, load_voice
from app.services.scoring import HOT_THRESHOLD, WARM_THRESHOLD, score_rules
from tests.test_scoring import make_lead, make_submission

# ── The files load and carry what the generator needs ─────────────────────────

def test_voice_names_the_reader_and_what_they_fear():
    reader = load_voice()["reader"]
    assert "Windows" in reader["is"]
    # The audience's first question about an automation product is what stops it. Copy
    # that does not know this writes as if nobody had ever been burned by software with
    # system privileges.
    assert "irreversible" in reader["is_afraid_of"]


def test_icp_states_both_who_it_is_for_and_who_it_is_not():
    icp = load_icp()
    assert icp["segments"], "no segments"
    assert icp["exclude"], "an ICP without exclusions is a wish list"
    assert any("not Windows" in item for item in icp["exclude"])


# ── Agreement with the lead scorer ────────────────────────────────────────────

def test_the_icp_floor_matches_what_the_scorer_actually_does():
    """icp.yaml says roughly 20 endpoints is the floor. The scorer caps below 20.

    Two statements of the same rule in two places is how a policy quietly becomes two
    policies — one that sales reads and one that ranks the leads.
    """
    assert any("20 endpoints" in item for item in load_icp()["exclude"])

    below_floor = score_rules(
        make_lead(), [make_submission("We have 12 Windows laptops and patching is manual.")]
    )
    assert below_floor.score < WARM_THRESHOLD, (
        "icp.yaml excludes fleets under ~20 endpoints; the scorer does not agree"
    )


def test_the_qualification_clauses_are_the_ones_the_scorer_scores():
    """The GTM bar has four clauses. Each must move the score, or the file is decoration."""
    clauses = load_icp()["qualifies_when"]
    assert len(clauses) == 4

    baseline = score_rules(
        make_lead(email="x@unknown-co.com", company=None),
        [make_submission("Please send information.")],
    )
    full = score_rules(
        make_lead(phone="+91 98110 00000"),
        [make_submission(
            "I am the Head of IT. We run 260 Windows laptops and the ticket backlog "
            "keeps growing. I own the budget.",
            interest="Endpoint Automation Assessment",
        )],
    )
    assert full.score >= HOT_THRESHOLD > baseline.score


# ── The prompt the generator is handed ────────────────────────────────────────

def test_the_prompt_carries_voice_and_audience_as_well_as_facts():
    prompt = brand_bible_prompt()

    assert "WHO IS READING" in prompt
    assert "HOW TO WRITE" in prompt
    assert "NEVER WRITE" in prompt
    assert "Evidence before action" in prompt
    assert "Endpoint Automation Assessment" in prompt
    # Facts alone produce accurate copy nobody wants to read.
    assert "Most of the day goes into collecting context" in prompt


@pytest.mark.parametrize("banned", ["fully autonomous", "zero-touch", "set and forget"])
def test_banned_phrases_are_named_in_the_prompt(banned: str):
    """Each of these claims something untrue, so the checker blocks or flags it. Naming
    them up front means a draft rarely reaches that point — cheaper than a revision loop."""
    assert banned in brand_bible_prompt()


def test_the_prompt_would_survive_its_own_checker():
    """The system prompt is text like any other.

    It quotes forbidden phrases in order to forbid them, so it cannot be blocker-free —
    but every blocker in it must come from the NEVER CLAIM section, not from a stray
    sentence elsewhere that states one as fact.
    """
    prompt = brand_bible_prompt()
    never_claim_section = prompt.split("NEVER CLAIM")[1].split("TRUE BUT UNPROVEN")[0]

    for finding in check_text(prompt).blockers:
        assert finding.matched in never_claim_section, (
            f"{finding.matched!r} appears outside the NEVER CLAIM section — the prompt "
            "is stating a forbidden claim rather than forbidding it"
        )
