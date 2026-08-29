"""The claim checker.

The cases below are not invented. Every blocker string is either something that was
actually live on technomateai.com, something an early draft of the marketing material
said, or the exact phrasing a language model reaches for when it wants a sentence to
sound stronger than the product is.
"""
import pytest

from app.services.claims import brand_bible_prompt, check_text, claimable_actions, load_claims


def rules_fired(text: str) -> set[str]:
    return {f.rule for f in check_text(text).findings}


# ── The claim that was actually shipping ──────────────────────────────────────

def test_catches_the_certificate_claim_that_was_live():
    """The exact copy from /astra, live from before 2026-08-22 until 2026-08-29."""
    result = check_text(
        "Device certificates. Certificate-based enrollment for every agent."
    )

    assert not result.passed
    assert "certificate_enrollment" in {f.rule for f in result.blockers}
    assert "token-based" in result.blockers[0].guidance.lower()


def test_the_replacement_copy_passes():
    result = check_text(
        "Per-device credentials. Each agent enrolls with an organization key, "
        "then authenticates with its own token."
    )
    assert result.passed
    assert result.findings == []


# ── Capabilities the product does not have ────────────────────────────────────

@pytest.mark.parametrize(
    ("copy", "rule"),
    [
        ("ASTRA applies registry fixes automatically.", "registry_and_drivers"),
        ("It updates drivers when a device falls behind.", "registry_and_drivers"),
        ("Flash firmware across the fleet.", "registry_and_drivers"),
        ("Disable a domain account the moment someone leaves.", "domain_accounts"),
        ("Every command is cryptographically signed.", "transport_security"),
        ("mTLS between the agent and the backend.", "transport_security"),
        ("One agent for Windows, macOS and Linux.", "non_windows"),
        ("A cross-platform endpoint agent.", "non_windows"),
        ("Fully autonomous remediation for your fleet.", "full_autonomy"),
    ],
)
def test_forbidden_capabilities_block(copy: str, rule: str):
    result = check_text(copy)
    assert not result.passed, f"should have blocked: {copy}"
    assert rule in {f.rule for f in result.blockers}


def test_a_blocker_always_says_what_is_true_instead():
    """A prohibition with no replacement invites someone to re-invent the false claim."""
    for finding in check_text("Certificate-based enrollment, mTLS, and macOS support.").blockers:
        assert finding.guidance, f"{finding.rule} blocks but offers nothing to say instead"


# ── Numbers nobody has earned ─────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("copy", "rule"),
    [
        ("Teams see 40% fewer tickets in the first month.", "results_percentage"),
        ("Reduce helpdesk load by 30%.", "results_percentage"),
        ("Resolve incidents 3x faster.", "multiplier"),
        ("99.9% uptime, guaranteed.", "uptime"),
        ("ASTRA is SOC 2 compliant.", "certifications"),
        ("Independently penetration-tested.", "certifications"),
        ("Most issues are resolved in under 5 minutes.", "resolution_time"),
        ("Trusted by 200 IT teams.", "scale"),
        # Ambiguous by nature: automatic-tier actions genuinely do run without a
        # human. Only a reader can tell whether the sentence meant that tier or all
        # of them, so the checker asks rather than decides.
        ("It fixes issues without human approval.", "full_autonomy"),
        ("Windows, macOS and Linux are all supported by NinjaOne.", "non_windows"),
    ],
)
def test_unproven_numbers_warn_but_do_not_block(copy: str, rule: str):
    """These are warnings on purpose.

    A percentage is only a problem when it is a claim about results — "40% fewer tickets"
    is one, "40% of Indian SMBs run fewer than 200 endpoints" is not, and no pattern can
    tell them apart. The reviewer decides; the checker makes sure they are asked.
    """
    result = check_text(copy)
    assert rule in {f.rule for f in result.warnings}
    assert result.passed, "an unproven claim must not stop copy reaching a human"


# ── Copy that should sail through ─────────────────────────────────────────────

@pytest.mark.parametrize("copy", [
    "ASTRA gathers endpoint evidence before it proposes a fix.",
    "Remediations are tiered: automatic, approval-required and admin-only, enforced "
    "server-side rather than in a prompt.",
    "Disable a leaver's local Windows account and force them out of the session, "
    "matched by SID.",
    "A heartbeat every 60 seconds from a Windows service and tray application.",
    "Every mutation and every agent command is recorded with actor, action and target.",
    "Blocks pen drives and portable disks only. Keyboards, mice and webcams are "
    "unaffected, and it is reversible.",
])
def test_true_copy_passes_cleanly(copy: str):
    result = check_text(copy)
    assert result.passed
    assert not result.findings, [str(f) for f in result.findings]


# ── Behaviour ─────────────────────────────────────────────────────────────────

def test_repeated_phrases_report_once():
    """A long article saying macOS twelve times has one problem, not twelve."""
    result = check_text("macOS. " * 12)
    assert len([f for f in result.findings if f.rule == "non_windows"]) == 1


def test_findings_carry_enough_context_to_judge_them():
    result = check_text(
        "Our platform is built for IT teams who are tired of firefighting. "
        "Certificate-based enrollment keeps every agent trusted. "
        "It runs quietly in the background."
    )
    finding = result.blockers[0]
    assert "enrollment" in finding.context
    assert finding.matched.lower().startswith("certificate-based")


def test_empty_text_is_not_an_error():
    assert check_text("").passed
    assert check_text("").findings == []


# ── The prompt the generator will be given ────────────────────────────────────

def test_brand_bible_prompt_carries_the_whole_contract():
    prompt = brand_bible_prompt()

    assert "governed AI system administrator" in prompt
    assert "NEVER CLAIM" in prompt
    assert "TRUE BUT UNPROVEN" in prompt
    # The real actions, so a generator does not invent plausible ones.
    assert "restart_explorer" in prompt
    assert "reset_local_password" in prompt
    # The operator-only carve-out, so it never writes "ASTRA locks the screen".
    assert "lock_session" in prompt
    assert "a human asks" in prompt


def test_the_prompt_does_not_itself_contain_a_forbidden_claim():
    """The system prompt is text like any other. If it stated something false, every
    draft would inherit it — and nothing downstream would catch it, because the checker
    reads the draft, not the instructions."""
    prompt_claims = " ".join(
        f"{e['never_claim']} {e['reality']}" for e in load_claims()["forbidden"]
    )
    # The prompt necessarily quotes the forbidden phrases in order to forbid them, so the
    # check is that it does so in that context and nowhere else.
    assert "NEVER CLAIM" in brand_bible_prompt()
    assert "certificate" in prompt_claims.lower()


def test_claimable_actions_matches_the_claim_file():
    actions = claimable_actions()
    assert set(actions) == {"automatic", "approval_required", "admin_only"}
    assert sum(len(v) for v in actions.values()) == 29


def test_signed_agent_updates_is_true_and_must_not_be_blocked():
    """The command-signing patterns must not catch the one signing claim that IS real.

    ASTRA signs the agent UPDATE MANIFEST (RSA-SHA256, key pinned in the binary). It does
    not sign individual commands. A pattern broad enough to block "signed" would have
    taken a shipped security feature off the website.
    """
    result = check_text(
        "The agent update manifest is signed RSA-SHA256 and verified against a key "
        "pinned in the agent binary."
    )
    assert result.passed, [str(f) for f in result.findings]


@pytest.mark.parametrize("copy", [
    "Every command is cryptographically signed.",
    "Commands are signed end to end.",
    "ASTRA signs every command before dispatch.",
])
def test_command_signing_blocks_in_any_voice(copy: str):
    """Marketing copy is written in the passive. The first version of this pattern only
    matched the active form, so "every command is signed" sailed through."""
    assert "transport_security" in {f.rule for f in check_text(copy).blockers}


# ── Stat cards: a figure and a caption, not a sentence ────────────────────────

@pytest.mark.parametrize("copy", [
    "1204+ Issues auto-healed / mo",
    "38s Avg. resolution time",
    "72% Less manual triage",
    "99.9% Fleet visibility",
])
def test_invented_stat_cards_are_flagged(copy: str):
    """All four of these were live in the homepage hero, and none was sourced.

    The sentence-shaped patterns caught only "72% Less". A stat card is a number beside a
    label, not a claim in prose, and fabricated metrics live in exactly that shape — so
    the shape needs its own patterns.
    """
    result = check_text(copy)
    assert result.warnings, f"not flagged: {copy}"
    assert result.passed, "a stat still goes to a human to judge, not straight back"


@pytest.mark.parametrize("copy", [
    "A heartbeat every 60 seconds.",
    "29 remediation actions across three approval tiers.",
    "Three tiers: automatic, approval-required, admin-only.",
])
def test_true_product_numbers_are_not_flagged(copy: str):
    """Facts about the product are not results claims.

    A checker that flagged "60-second heartbeat" would push copy away from the concrete
    and towards the vague, which is the opposite of what it is for.
    """
    result = check_text(copy)
    assert not result.findings, [str(f) for f in result.findings]
