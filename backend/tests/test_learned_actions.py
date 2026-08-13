"""The learning loop: when the LLM fixes an issue the built-in rules can't classify,
the fix is remembered so the same kind of issue is handled for free next time."""
from sqlalchemy import select

from app.core.security import hash_opaque_token
from app.models import Device, LearnedAction, RemediationStatus, RemediationTask
from app.services.ai.provider import LLMResponse, StubProvider, ToolCall
from app.services.conversations import ConversationService


class _FakeLLM:
    """Stands in for Claude — not a StubProvider, so the router treats it as the
    learnable LLM path. Proposes a service restart for an unlisted issue."""

    async def generate(self, *, system, messages, tools):
        results = StubProvider._extract_tool_results(messages[-1])
        if results is not None:
            # Relay what the tool actually said. A real model tells the user when a fix was
            # refused because one is already running; a fake that always answers "All done"
            # would let that message go missing without any test noticing.
            return LLMResponse(text=" ".join(results) or "All done.")
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


async def _device_reports_success(session_factory, hostname="PRINT-PC"):
    """Drive the fix all the way to a confirmed result, the way the agent does.

    Setting the status by hand would skip record_result, and record_result is where
    learning now happens — a fix is remembered because a device ran it and said it worked,
    not because the model suggested it.
    """
    from app.services.remediation.service import RemediationService

    async with session_factory() as session:
        device = (
            await session.execute(select(Device).where(Device.hostname == hostname))
        ).scalar_one()
        task = (await session.execute(select(RemediationTask))).scalars().first()
        task.status = RemediationStatus.DISPATCHED
        await session.commit()
        await RemediationService(session).record_result(
            device=device, task_id=task.id, success=True, output="Spooler restarted",
        )


async def test_a_proposed_fix_is_not_learned_until_a_device_confirms_it(
    session_factory, admin_user
):
    """A queued fix is an intention. Learning from it would auto-apply it forever on the
    strength of something no machine ever ran."""
    async with session_factory() as session:
        device = await _make_device(session, admin_user.org_id)
        svc = ConversationService(session, provider=_FakeLLM())
        _, _, source = await svc.device_chat(device=device, content=_QUERY, conversation_id=None)
        assert source == "engine"

        learned = (await session.execute(select(LearnedAction))).scalars().all()
        assert learned == [], "nothing has run yet — there is nothing to have learned"


async def test_a_confirmed_llm_fix_is_learned_then_reused_for_free(
    session_factory, admin_user
):
    # 1. The LLM solves the unlisted issue by restarting a service...
    async with session_factory() as session:
        device = await _make_device(session, admin_user.org_id)
        svc = ConversationService(session, provider=_FakeLLM())
        _, _, source = await svc.device_chat(device=device, content=_QUERY, conversation_id=None)
        assert source == "engine"

    # ...and the device runs it and reports back. THAT is what teaches the store — and it
    # also clears the way for the second turn, which would otherwise be refused as a
    # duplicate: someone reporting the same problem while the fix is still queued should be
    # told it is already under way, not have it queued again.
    await _device_reports_success(session_factory)

    async with session_factory() as session:
        learned = (await session.execute(select(LearnedAction))).scalars().all()
        assert len(learned) == 1, "a confirmed fix should have been learned"
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

        tasks = (await session.execute(select(RemediationTask))).scalars().all()
        assert len(tasks) == 2
        assert all(t.action_id == "restart_service" for t in tasks)


async def test_a_repeat_report_does_not_queue_the_fix_twice(session_factory, admin_user):
    """Reporting the same problem again while the fix is still queued must not queue it
    again. The user hasn't seen it work yet — that's precisely why they're asking again —
    and a second identical action only ties the device up for longer.

    Both turns go through the model here. The first fix is deliberately left unconfirmed,
    so nothing has been learned and the guard is the only thing that can stop the repeat.
    """
    async with session_factory() as session:
        device = await _make_device(session, admin_user.org_id)
        svc = ConversationService(session, provider=_FakeLLM())
        await svc.device_chat(device=device, content=_QUERY, conversation_id=None)

    async with session_factory() as session:
        device = (
            await session.execute(select(Device).where(Device.hostname == "PRINT-PC"))
        ).scalar_one()
        svc = ConversationService(session, provider=_FakeLLM())
        _, msg, _ = await svc.device_chat(device=device, content=_QUERY, conversation_id=None)

        tasks = (await session.execute(select(RemediationTask))).scalars().all()
        assert len(tasks) == 1, "the same fix must not be queued twice while it's in flight"
        # And the user is told why, rather than being left thinking nothing happened.
        assert "already" in msg.content.lower()


async def test_global_fix_auto_applies_for_any_org(session_factory, admin_user):
    """A fix the operator curates globally is applied automatically for an org that
    never learned it — no LLM call."""
    from sqlalchemy import select
    from app.models import RemediationTask
    from app.services.ai.learned import LearnedFixStore

    # An unlisted problem (built-in rules can't classify it) with a known fix.
    problem = "the label printer only feeds blank stickers"

    async with session_factory() as session:
        await LearnedFixStore(session).create_global(
            problem=problem, action_id="restart_service", params={"service_name": "Spooler"}
        )

    async with session_factory() as session:
        device = await _make_device(session, admin_user.org_id, hostname="OPS-PC")
        # No API key -> no LLM; the GLOBAL fix must catch this before any LLM path.
        svc = ConversationService(session)
        _, _, source = await svc.device_chat(device=device, content=problem, conversation_id=None)
        assert source == "learned", f"global fix should have applied; got source={source}"
        tasks = (await session.execute(select(RemediationTask))).scalars().all()
        assert len(tasks) == 1
        assert tasks[0].action_id == "restart_service"
        assert tasks[0].params == {"service_name": "Spooler"}


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
