"""The learning loop: when the LLM fixes an issue the built-in rules can't classify,
the fix is remembered so the same kind of issue is handled for free next time."""
from sqlalchemy import select

from app.core.security import hash_opaque_token
from app.models import Device, LearnedAction, RemediationTask
from app.services.ai.provider import LLMResponse, StubProvider, ToolCall
from app.services.conversations import ConversationService


class _FakeLLM:
    """Stands in for Claude — not a StubProvider, so the router treats it as the
    learnable LLM path. Proposes a service restart for an unlisted issue."""

    async def generate(self, *, system, messages, tools):
        if StubProvider._extract_tool_results(messages[-1]) is not None:
            return LLMResponse(text="All done.")
        return LLMResponse(
            text="Restarting the print spooler.",
            tool_calls=[ToolCall(
                id="1", name="propose_remediation",
                input={"action_id": "restart_service", "service_name": "Spooler",
                       "reason": "print queue jammed"},
            )],
        )


# An unlisted issue: no app name, no problem-word, no diagnostic keyword -> the
# built-in can_handle returns False, so it would normally go to the LLM.
_QUERY = "the print queue is completely jammed and pages pile up"


async def _make_device(session, org_id, hostname="PRINT-PC"):
    device = Device(
        org_id=org_id, hostname=hostname, machine_id=hostname.lower(),
        os_version="Windows 11", agent_version="0.1.0",
        token_hash=hash_opaque_token(hostname),
    )
    session.add(device)
    await session.flush()
    await session.commit()
    return device


async def test_llm_fix_is_learned_then_reused_for_free(session_factory, admin_user):
    # 1. The LLM solves the unlisted issue by restarting a service -> it's learned.
    async with session_factory() as session:
        device = await _make_device(session, admin_user.org_id)
        svc = ConversationService(session, provider=_FakeLLM())
        _, _, source = await svc.device_chat(device=device, content=_QUERY, conversation_id=None)
        assert source == "engine"

        learned = (await session.execute(select(LearnedAction))).scalars().all()
        assert len(learned) == 1
        assert learned[0].action_id == "restart_service"
        assert learned[0].params == {"service_name": "Spooler"}

    # 2. A fresh service with NO LLM provider sees the same issue -> handled for free
    #    from the learned store (no LLM call), and it applies the same fix.
    async with session_factory() as session:
        device = (
            await session.execute(select(Device).where(Device.hostname == "PRINT-PC"))
        ).scalar_one()
        svc = ConversationService(session)  # no injected provider, no API key
        _, msg, source = await svc.device_chat(device=device, content=_QUERY, conversation_id=None)
        assert source == "learned", "the repeat issue should be served from the learned store"

        # Both turns created a remediation task (the LLM's, then the free learned reuse).
        tasks = (await session.execute(select(RemediationTask))).scalars().all()
        assert len(tasks) == 2
        assert all(t.action_id == "restart_service" for t in tasks)


async def test_common_issue_never_becomes_a_learned_entry(session_factory, admin_user):
    # A listed/common issue ("excel not working") is handled by the built-in rules,
    # so nothing new is learned.
    async with session_factory() as session:
        device = await _make_device(session, admin_user.org_id, hostname="XL-PC")
        svc = ConversationService(session)  # no provider -> built-in rules
        _, _, source = await svc.device_chat(
            device=device, content="excel not working", conversation_id=None
        )
        assert source == "engine"
        learned = (await session.execute(select(LearnedAction))).scalars().all()
        assert learned == []
