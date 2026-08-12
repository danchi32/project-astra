"""The Windows expert brief is for the model, and only for the model.

The built-in providers answer from keyword rules and never read a system prompt, so sending
it to them would be several thousand tokens describing a job they are not doing. It also
states the point of the thing: a problem reaches the model precisely because the rules
could not place it.
"""
from app.services.ai.cognitive import SYSTEM_PROMPT, CognitiveEngine
from app.services.ai.prompts import WINDOWS_EXPERT_PROMPT
from app.services.ai.provider import (
    AnthropicProvider,
    LearnedActionProvider,
    StubProvider,
)


def _engine_with(provider) -> CognitiveEngine:
    engine = CognitiveEngine.__new__(CognitiveEngine)
    engine.provider = provider
    return engine


def test_the_expert_brief_goes_to_the_model():
    assert _engine_with(AnthropicProvider("k", "m", 1))._is_real_llm() is True


def test_the_built_in_paths_do_not_get_it():
    assert _engine_with(StubProvider())._is_real_llm() is False
    assert _engine_with(LearnedActionProvider("restart_outlook", {}))._is_real_llm() is False


def test_the_brief_does_not_undo_what_the_product_enforces():
    """Three things the source document got wrong for this product, pinned so a later edit
    that pastes it back in fails here rather than in a customer's chat."""
    lowered = WINDOWS_EXPERT_PROMPT.lower()

    # The agent runs an allowlist. The source document handed out PowerShell, which either
    # does nothing or talks a user into running it themselves — so the brief has to say
    # both halves: you cannot run commands, and you must not delegate them either.
    assert "cannot run arbitrary commands" in lowered
    assert "must not tell the user to run one instead" in lowered

    # Escalation is a tool call. "Recommend escalation" is what left offers unanswerable.
    assert "escalation tool" in lowered
    assert "a question you write yourself cannot be answered" in lowered

    # The tool's "applied automatically" means queued, and saying otherwise was a real bug.
    assert "queued to run" in lowered


def test_the_brief_still_says_what_it_was_adopted_for():
    lowered = WINDOWS_EXPERT_PROMPT.lower()
    for idea in ("diagnose first", "root cause", "evidence", "rank them", "verify"):
        assert idea in lowered, f"the brief lost {idea!r}"
    assert len(WINDOWS_EXPERT_PROMPT) > len(SYSTEM_PROMPT)
