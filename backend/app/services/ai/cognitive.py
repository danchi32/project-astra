"""The ASTRA cognitive engine: an agentic tool-use loop over read-only evidence tools."""
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import AssistantVersion
from app.services.ai.prompts import WINDOWS_EXPERT_PROMPT
from app.services.ai.provider import (
    LearnedActionProvider,
    LLMProvider,
    StubProvider,
    get_provider,
)
from app.services.ai.tools import TOOL_SCHEMAS, dispatch_tool

logger = logging.getLogger("astra.cognitive")

SYSTEM_PROMPT = """You are ASTRA, an enterprise AI System Administrator.

Your job is to help the user diagnose problems and GET THINGS DONE on managed Windows devices — you take actions, you don't just hand out instructions.

When a user reports a problem or asks you to do something, follow this shape every time:
1. UNDERSTAND what they actually want.
2. GATHER what you need before acting:
   - If completing the task requires details the user hasn't given, ASK them for the missing pieces — a short, specific question, one step at a time. For example, creating a mail rule needs BOTH the sender's email address AND the destination folder; if either is missing, ask for it. NEVER guess a required value (an email address, a folder name, an app name) and never act on incomplete information.
   - For a diagnostic problem, gather evidence first with the tools (telemetry, event log). Never speculate when you can check.
   - Check the knowledge base for a documented runbook before answering a how-to or inventing a solution.
3. ACT once — and only once — you have everything you need: use the right tool to actually perform the task (e.g. propose_remediation), not just describe the steps.
4. CONFIRM based on what the tool actually reported — and be precise about tense:
   - If the fix was applied automatically, the agent on the device still has to RUN it. So say you're ON IT, not that it's finished — e.g. "On it — I'm creating that rule now; I'll confirm here the moment it's done on your device." The system posts the real "✅ done" / "⚠️ couldn't" result into this chat once the device reports back, so you must NOT pre-announce success.
   - If it was queued for IT approval instead, say that plainly.
   - NEVER claim something succeeded, finished, or is "done" that the tool did not confirm. "Applied automatically" from the tool means QUEUED-TO-RUN, not completed.

Other principles:
- Safe, reversible fixes (restart an app, flush DNS, clear temp, create a mail rule) run automatically; higher-risk fixes are queued for the IT team — the tool result tells you which, so report it accurately.
- Prefer the least-disruptive fix that addresses the cause, and only act on evidence.
- Be concise and specific; reference the actual numbers you observed (CPU %, RAM %, disk free, event IDs).
- Speak to the end user in plain, friendly language — no jargon.
"""


@dataclass
class EngineResult:
    text: str
    tool_trail: list[dict[str, Any]] = field(default_factory=list)
    cacheable: bool = True  # False for error/unavailable answers — never cache those


class CognitiveEngine:
    def __init__(
        self,
        session: AsyncSession,
        provider: LLMProvider | None = None,
        version: AssistantVersion | None = None,
    ) -> None:
        """`version` is the published assistant configuration to run as.

        None means "run as ASTRA has always run": the constants below and every tool the
        engine advertises. That is what lets this parameter be added to a live system —
        the absent case is the current case, not a new one.
        """
        self.session = session
        self.provider = provider or get_provider()
        settings = get_settings()
        defaults = {
            "system_prompt": WINDOWS_EXPERT_PROMPT,
            "max_tool_iterations": settings.ai_max_tool_iterations,
        }
        resolved = (
            version.resolved(defaults=defaults)
            if version is not None
            else {**defaults, "tool_ids": None}
        )
        self.brief = resolved["system_prompt"]
        self.max_iterations = resolved["max_tool_iterations"]
        # None = every tool the engine advertises. A list NARROWS that set and can never
        # widen it: the remediation registry's tier and operator_only rules are applied
        # upstream in tools.py, so an id named here that the registry withholds stays
        # withheld. A grant is a filter, not a privilege.
        self.tool_ids = resolved["tool_ids"]

    def _is_real_llm(self) -> bool:
        """True when the provider is an actual model rather than the built-in rules.

        Same test conversations.py uses to decide what is worth learning from — the
        built-in paths are deterministic and teach nothing, and they read no prompt.
        """
        return not isinstance(self.provider, (StubProvider, LearnedActionProvider))

    async def run(
        self,
        *,
        org_id: uuid.UUID,
        history: list[dict[str, Any]],
        user_message: str,
        device_hostname: str | None = None,
        acting_device_id: uuid.UUID | None = None,
        conversation_id: uuid.UUID | None = None,
    ) -> EngineResult:
        """Run one assistant turn: reason, call evidence tools as needed, and reply.

        `history` is prior user/assistant text turns in Anthropic wire format.
        When `device_hostname` is set (tray chat), the AI focuses on that device.
        """
        # The expert brief is for the model and nobody else. The built-in providers answer
        # from keyword rules and ignore a system prompt entirely, so sending it to them
        # would be several thousand tokens describing a job they are not doing — and it
        # would blur what reaching the model is FOR. A problem only gets here because the
        # rules could not place it.
        brief = self.brief if self._is_real_llm() else SYSTEM_PROMPT

        messages: list[dict[str, Any]] = [*history, {"role": "user", "content": user_message}]
        trail: list[dict[str, Any]] = []

        # Escalation is only offered to organizations that can actually file a ticket, and
        # only when we know whose ticket it would be. Withholding the tool is the guard:
        # a model that cannot see it cannot promise a ticket nobody can raise.
        from app.services.ai import escalation_tools

        tools = TOOL_SCHEMAS + await escalation_tools.available_for(
            self.session, org_id=org_id, conversation_id=conversation_id,
            device_id=acting_device_id,
        )
        # An assistant's grant narrows the advertised set. Applied HERE, before the
        # escalation wording below is decided, so the two can never disagree — an assistant
        # not granted the offer tool must not be told to call it.
        if self.tool_ids is not None:
            allowed = set(self.tool_ids)
            tools = [t for t in tools if t["name"] in allowed]
        if any(t["name"] == escalation_tools.OFFER for t in tools):
            # "Ask first, then call the tool" is what this used to say, and the model did
            # exactly that: it wrote "shall I raise a ticket?" in its own words and called
            # nothing, so no offer was recorded and the user's yes had nothing to act on.
            # Asking and calling are the same act, and the wording has to say so.
            #
            # Saying it was not quite enough. Measured over ten runs of the same complaint,
            # the tool was called in eight — and the two misses were the two longest
            # replies. Every reply that called it was under 350 characters; the ones that
            # explained workarounds first ran to 900 and asked in prose at the end. So the
            # ordering is stated too: the call comes before the prose, not after it.
            brief += (
                "\n\nIf you cannot fix the problem — a fix failed, no fix exists, or the "
                "user says it is still broken after one worked — offer to raise a ticket "
                f"with their IT helpdesk by calling {escalation_tools.OFFER}.\n"
                "Call it FIRST, before you write the reply. Not after explaining the "
                "problem, not after listing workarounds — those come afterwards and can be "
                "brief. A long reply that ends by asking about a ticket is the failure "
                "mode: the question never gets recorded.\n"
                "That call IS the question. It puts it to the user and records it. Never "
                "write the question yourself instead: an unrecorded question cannot be "
                "answered, so their 'yes' would be lost and they would be asked twice. If "
                "your reply is about to ask whether to raise a ticket, call the tool and "
                f"let it ask.\nWhen they agree, call {escalation_tools.RAISE}. Never claim "
                "a ticket has been raised unless the tool told you it was."
            )

        # The brief and every tool schema are resent on each pass of the tool-use loop, so
        # the same few thousand tokens are billed three to five times a conversation. They
        # are also byte-identical across the whole fleet, which is what makes them worth
        # caching — and caching is a prefix match, so the arrangement below is the point:
        # the invariant text comes first and carries the breakpoint, and the one sentence
        # that names a device comes after it. Written the other way round the hostname
        # would sit inside the cached prefix, and nineteen machines would mean nineteen
        # separate copies of an identical brief, each read only by its own device.
        # Tools render ahead of the system prompt, so this one breakpoint covers both.
        system: list[dict[str, Any]] = [
            {"type": "text", "text": brief, "cache_control": {"type": "ephemeral"}}
        ]
        if device_hostname:
            system.append({"type": "text", "text": (
                f"The person chatting with you is the logged-in user of device "
                f"'{device_hostname}'. They are reporting a problem on THIS device. Focus your "
                f"investigation on '{device_hostname}' unless they explicitly ask about another. "
                f"Speak to them as the end user (not an IT admin): be friendly and avoid jargon."
            )})

        try:
            for _ in range(self.max_iterations):
                response = await self.provider.generate(
                    system=system, messages=messages, tools=tools
                )

                if not response.tool_calls:
                    return EngineResult(text=response.text, tool_trail=trail)

                # Record the assistant's tool-use turn.
                assistant_content: list[dict[str, Any]] = []
                if response.text:
                    assistant_content.append({"type": "text", "text": response.text})
                for call in response.tool_calls:
                    assistant_content.append(
                        {"type": "tool_use", "id": call.id, "name": call.name, "input": call.input}
                    )
                messages.append({"role": "assistant", "content": assistant_content})

                # Execute each tool and feed results back.
                tool_results: list[dict[str, Any]] = []
                for call in response.tool_calls:
                    output = await dispatch_tool(
                        session=self.session, org_id=org_id, name=call.name,
                        tool_input=call.input, acting_device_id=acting_device_id,
                        conversation_id=conversation_id,
                    )
                    trail.append({"tool": call.name, "input": call.input, "output": output})
                    tool_results.append(
                        {"type": "tool_result", "tool_use_id": call.id, "content": output}
                    )
                messages.append({"role": "user", "content": tool_results})
        except Exception:
            # An LLM/provider failure (auth, billing, rate limit, network) must not crash
            # the request — degrade to a friendly message for the end user; operators see
            # the full stack in the logs.
            logger.exception("Cognitive engine provider call failed")
            return EngineResult(
                text="I'm sorry — I couldn't finish looking into this because the AI service is "
                "temporarily unavailable. Please try again in a few minutes, or contact your IT "
                "team if it keeps happening.",
                tool_trail=trail,
                cacheable=False,
            )

        # Iteration cap hit — return whatever the last text was.
        return EngineResult(
            text="I gathered evidence but need to stop here to avoid an overly long investigation. "
            "Ask a more specific follow-up and I'll continue.",
            tool_trail=trail,
            cacheable=False,
        )
