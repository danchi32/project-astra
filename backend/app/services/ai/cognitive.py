"""The ASTRA cognitive engine: an agentic tool-use loop over read-only evidence tools."""
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.ai.provider import LLMProvider, get_provider
from app.services.ai.tools import TOOL_SCHEMAS, dispatch_tool

logger = logging.getLogger("astra.cognitive")

SYSTEM_PROMPT = """You are ASTRA, an enterprise AI System Administrator.

Your job is to help diagnose and fix problems on managed Windows devices. Follow these principles:
- Evidence before action: gather telemetry and event-log evidence with the provided tools before drawing conclusions or applying a fix. Never speculate when you can check.
- You can apply fixes with the propose_remediation tool. Safe, reversible fixes (restart an app, flush DNS, clear temp files) run automatically; higher-risk fixes are queued for the IT team to approve — the tool result tells you which happened, so report it accurately. Never claim you fixed something the tool didn't confirm.
- Only propose a remediation you have evidence for, and prefer the least-disruptive fix that addresses the cause.
- Be concise and specific. Reference the actual numbers you observed (CPU %, RAM %, disk free, event IDs).
- If you lack evidence to answer, say what you would need to check.
"""


@dataclass
class EngineResult:
    text: str
    tool_trail: list[dict[str, Any]] = field(default_factory=list)


class CognitiveEngine:
    def __init__(self, session: AsyncSession, provider: LLMProvider | None = None) -> None:
        self.session = session
        self.provider = provider or get_provider()
        self.max_iterations = get_settings().ai_max_tool_iterations

    async def run(
        self,
        *,
        org_id: uuid.UUID,
        history: list[dict[str, Any]],
        user_message: str,
        device_hostname: str | None = None,
        acting_device_id: uuid.UUID | None = None,
    ) -> EngineResult:
        """Run one assistant turn: reason, call evidence tools as needed, and reply.

        `history` is prior user/assistant text turns in Anthropic wire format.
        When `device_hostname` is set (tray chat), the AI focuses on that device.
        """
        system = SYSTEM_PROMPT
        if device_hostname:
            system += (
                f"\n\nThe person chatting with you is the logged-in user of device "
                f"'{device_hostname}'. They are reporting a problem on THIS device. Focus your "
                f"investigation on '{device_hostname}' unless they explicitly ask about another. "
                f"Speak to them as the end user (not an IT admin): be friendly and avoid jargon."
            )

        messages: list[dict[str, Any]] = [*history, {"role": "user", "content": user_message}]
        trail: list[dict[str, Any]] = []

        try:
            for _ in range(self.max_iterations):
                response = await self.provider.generate(
                    system=system, messages=messages, tools=TOOL_SCHEMAS
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
            )

        # Iteration cap hit — return whatever the last text was.
        return EngineResult(
            text="I gathered evidence but need to stop here to avoid an overly long investigation. "
            "Ask a more specific follow-up and I'll continue.",
            tool_trail=trail,
        )
