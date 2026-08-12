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


async def test_the_cached_part_of_the_prompt_names_no_device(session_factory, admin_user):
    """The hostname must fall outside the cache breakpoint, and nothing enforces that but
    the order the blocks are built in.

    Caching is a prefix match, so a device name inside the cached block would give every
    machine its own private copy of a brief that is identical on all of them — read only
    by that one device, rewritten whenever it goes cold. Nothing would break: replies stay
    correct and the tests still pass, the bill just quietly stops improving. That is
    precisely why it is pinned here, where moving the sentence back fails loudly.
    """
    seen: list[list[dict]] = []

    class _Recorder(StubProvider):
        async def generate(self, *, system, messages, tools):
            seen.append(system)
            return await super().generate(system=system, messages=messages, tools=tools)

    async with session_factory() as session:
        await CognitiveEngine(session, _Recorder()).run(
            org_id=admin_user.org_id, history=[], user_message="hello",
            device_hostname="LAPTOP-042",
        )

    assert seen, "the engine never called the provider"
    system = seen[0]
    assert isinstance(system, list), "a plain string carries no cache breakpoint"

    cached = [b for b in system if b.get("cache_control")]
    assert len(cached) == 1, "exactly one breakpoint — tools render ahead of it, so one covers both"
    assert system[0] is cached[0], "anything before the breakpoint is what gets cached"

    assert "LAPTOP-042" not in cached[0]["text"], \
        "the device name is inside the cached prefix — that is one cache entry per machine"
    assert any("LAPTOP-042" in b["text"] for b in system[1:]), \
        "the model still has to be told which device it is looking at"
