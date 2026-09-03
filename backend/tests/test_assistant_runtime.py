"""The engine runs an assistant version — and running the seeded one changes nothing.

Two claims are pinned here, and they are the whole reason this slice is safe to ship:

  1. EQUIVALENCE. With the built-in version seeded from the same constants the engine falls
     back to, every input to the model is byte-identical to what it was before assistant
     versions existed. "Nothing broke" is verified, not believed.
  2. ISOLATION. A grant narrows the advertised tool set, and cannot widen it. An assistant
     that was not given a tool never sees it, and the registry's own withholding survives
     any grant.
"""
import pytest

from app.models import Assistant, AssistantVersion, AssistantVersionStatus
from app.services.ai.cognitive import CognitiveEngine
from app.services.ai.prompts import WINDOWS_EXPERT_PROMPT
from app.services.ai.provider import LLMResponse
from app.services.remediation.actions import ACTIONS, RemediationTier


class Recorder:
    """A provider that looks like a real model to `_is_real_llm()`.

    Deliberately NOT a StubProvider subclass: the built-in providers read no system prompt,
    so a stub-derived recorder would capture the fallback constant and prove nothing about
    what an assistant version sends.
    """

    def __init__(self) -> None:
        self.system: list = []
        self.tools: list = []

    async def generate(self, *, system, messages, tools):
        self.system.append(system)
        self.tools.append(tools)
        return LLMResponse(text="done")


async def _capture(session, org_id, version=None) -> Recorder:
    recorder = Recorder()
    engine = CognitiveEngine(session, recorder, version=version)
    await engine.run(org_id=org_id, history=[], user_message="my laptop is slow")
    assert recorder.system, "the engine never called the provider"
    return recorder


async def _seed_builtin(session_factory, **version_fields) -> AssistantVersion:
    async with session_factory() as session:
        assistant = Assistant(org_id=None, name="ASTRA System Administrator")
        session.add(assistant)
        await session.flush()
        version = AssistantVersion(
            assistant_id=assistant.id, version_no=1,
            status=AssistantVersionStatus.PUBLISHED, **version_fields,
        )
        session.add(version)
        await session.flush()
        assistant.published_version_id = version.id
        await session.commit()
        return version


@pytest.mark.asyncio
async def test_seeded_version_is_byte_identical_to_the_constants(session_factory, admin_user):
    """The equivalence gate. If this fails, the refactor changed behaviour."""
    version = await _seed_builtin(session_factory, system_prompt=WINDOWS_EXPERT_PROMPT)

    async with session_factory() as session:
        before = await _capture(session, admin_user.org_id, version=None)
        after = await _capture(session, admin_user.org_id, version=version)

    assert after.system[0] == before.system[0], "the system blocks changed"
    assert after.tools[0] == before.tools[0], "the advertised tool set changed"


@pytest.mark.asyncio
async def test_null_columns_fall_back_to_server_defaults(session_factory, admin_user):
    """A version of all NULLs is the current behaviour, not an empty one."""
    from app.core.config import get_settings

    version = await _seed_builtin(session_factory)  # every behaviour column NULL

    async with session_factory() as session:
        engine = CognitiveEngine(session, Recorder(), version=version)
        assert engine.brief == WINDOWS_EXPERT_PROMPT
        assert engine.max_iterations == get_settings().ai_max_tool_iterations
        assert engine.tool_ids is None

        captured = await _capture(session, admin_user.org_id, version=version)
        default = await _capture(session, admin_user.org_id, version=None)
        assert captured.tools[0] == default.tools[0]


@pytest.mark.asyncio
async def test_a_grant_narrows_the_advertised_tools(session_factory, admin_user):
    version = await _seed_builtin(
        session_factory, tool_ids=["list_devices", "search_knowledge_base"]
    )

    async with session_factory() as session:
        captured = await _capture(session, admin_user.org_id, version=version)

    names = {t["name"] for t in captured.tools[0]}
    assert names == {"list_devices", "search_knowledge_base"}
    assert "propose_remediation" not in names, "an ungranted tool reached the model"


@pytest.mark.asyncio
async def test_an_empty_grant_is_not_the_same_as_no_grant(session_factory, admin_user):
    """`[]` means "may call nothing" — a legitimate answer-only assistant. NULL means "all"."""
    version = await _seed_builtin(session_factory, tool_ids=[])

    async with session_factory() as session:
        captured = await _capture(session, admin_user.org_id, version=version)

    assert captured.tools[0] == []


@pytest.mark.asyncio
async def test_a_grant_cannot_invent_a_tool(session_factory, admin_user):
    """Naming a tool that does not exist does not create it. A grant is a filter."""
    version = await _seed_builtin(
        session_factory, tool_ids=["list_devices", "delete_everything", "run_powershell"]
    )

    async with session_factory() as session:
        captured = await _capture(session, admin_user.org_id, version=version)

    assert {t["name"] for t in captured.tools[0]} == {"list_devices"}


@pytest.mark.asyncio
async def test_a_grant_cannot_reach_a_withheld_action(session_factory, admin_user):
    """The registry's withholding outranks any grant.

    Granting `propose_remediation` hands over the tool, not the catalogue: admin-only and
    operator-only actions are filtered out in tools.py where the schema is built, so no row
    a tenant can write puts them back.
    """
    version = await _seed_builtin(session_factory, tool_ids=["propose_remediation"])

    async with session_factory() as session:
        captured = await _capture(session, admin_user.org_id, version=version)

    schema = next(t for t in captured.tools[0] if t["name"] == "propose_remediation")
    offered = set(schema["input_schema"]["properties"]["action_id"]["enum"])

    withheld = {
        a.id for a in ACTIONS.values()
        if a.tier is RemediationTier.ADMIN_ONLY or a.operator_only
    }
    assert withheld, "the registry withholds nothing — this test would pass vacuously"
    assert not (offered & withheld), f"a grant exposed withheld actions: {offered & withheld}"


@pytest.mark.asyncio
async def test_conversations_run_the_seeded_builtin(session_factory, admin_user):
    """The selection rule: the platform's own published assistant, or None when unseeded."""
    from app.services.assistants import AssistantService

    async with session_factory() as session:
        assert await AssistantService(session).published_builtin() is None

    version = await _seed_builtin(session_factory, system_prompt=WINDOWS_EXPERT_PROMPT)

    async with session_factory() as session:
        found = await AssistantService(session).published_builtin()
        assert found is not None and found.id == version.id


@pytest.mark.asyncio
async def test_a_version_may_lower_the_step_cap_but_not_raise_it(session_factory):
    """Each iteration is a billed model call, so the server setting is a ceiling.

    Clamped in `resolved()` as well as refused at the API: a row written by a seed script
    or a fixture never reaches the API validator, and the cost lever has to hold either way.
    """
    from app.core.config import get_settings

    ceiling = get_settings().ai_max_tool_iterations

    lowered = await _seed_builtin(session_factory, max_tool_iterations=1)
    async with session_factory() as session:
        assert CognitiveEngine(session, Recorder(), version=lowered).max_iterations == 1

    raised = AssistantVersion(
        assistant_id=lowered.assistant_id, version_no=99,
        status=AssistantVersionStatus.DRAFT, max_tool_iterations=ceiling + 50,
    )
    async with session_factory() as session:
        assert CognitiveEngine(session, Recorder(), version=raised).max_iterations == ceiling


@pytest.mark.asyncio
async def test_the_api_refuses_a_raised_step_cap(client, admin_headers):
    from app.core.config import get_settings

    created = await client.post(
        "/api/v1/assistants", json={"name": "Expensive"}, headers=admin_headers
    )
    refused = await client.post(
        f"/api/v1/assistants/{created.json()['id']}/versions",
        json={"max_tool_iterations": get_settings().ai_max_tool_iterations + 1},
        headers=admin_headers,
    )
    assert refused.status_code == 422
    assert "server limit" in refused.text


@pytest.mark.asyncio
async def test_the_api_refuses_an_unwired_model_override(client, admin_headers):
    """Refuse rather than accept and ignore — a silently dropped model setting reads as
    'the cheaper model made no difference' instead of 'the platform ignored you'."""
    created = await client.post(
        "/api/v1/assistants", json={"name": "Router"}, headers=admin_headers
    )
    refused = await client.post(
        f"/api/v1/assistants/{created.json()['id']}/versions",
        json={"model": "claude-haiku-4-5-20251001"}, headers=admin_headers,
    )
    assert refused.status_code == 422
    assert "not configurable yet" in refused.text
