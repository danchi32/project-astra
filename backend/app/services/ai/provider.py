"""LLM provider abstraction for the ASTRA cognitive engine.

The engine is a provider-agnostic agentic tool-use loop. `AnthropicProvider` calls
Claude via the official SDK; `StubProvider` is deterministic and lets the platform
run in tests and local demos without an API key or network access.
"""
import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.config import get_settings


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMProvider(Protocol):
    async def generate(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        """Given the system prompt, conversation messages (Anthropic wire format),
        and tool schemas, return the assistant's next turn."""
        ...


class AnthropicProvider:
    """Calls Claude via the official Anthropic SDK."""

    def __init__(self, api_key: str, model: str, max_tokens: int) -> None:
        # Imported lazily so the package is only required when a key is configured.
        import anthropic

        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    async def generate(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=messages,
            tools=tools,
        )
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, input=dict(block.input)))
        return LLMResponse(text="".join(text_parts), tool_calls=tool_calls)


class StubProvider:
    """Deterministic provider for tests and no-key local runs.

    Mimics the evidence-before-action loop: on a diagnostic question it gathers
    device telemetry via tools, then summarizes. Behaviour is a pure function of
    the message history so tests are stable.
    """

    _DIAGNOSTIC_KEYWORDS = (
        "cpu", "ram", "memory", "disk", "slow", "performance", "health",
        "telemetry", "device", "status", "event", "error",
    )

    async def generate(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        last = messages[-1]

        # If we just received tool results, summarize them and finish.
        tool_results = self._extract_tool_results(last)
        if tool_results is not None:
            return LLMResponse(text=self._summarize(tool_results))

        # Otherwise inspect the latest user text.
        user_text = self._latest_user_text(messages).lower()
        if any(kw in user_text for kw in self._DIAGNOSTIC_KEYWORDS):
            return LLMResponse(
                text="Let me gather the current device telemetry before answering.",
                tool_calls=[ToolCall(id="stub-tool-1", name="list_devices", input={})],
            )

        return LLMResponse(
            text=(
                "Hello, I'm ASTRA, your AI system administrator. Ask me about a device's "
                "health, performance, or recent errors and I'll investigate."
            )
        )

    @staticmethod
    def _extract_tool_results(message: dict[str, Any]) -> list[str] | None:
        if message.get("role") != "user" or not isinstance(message.get("content"), list):
            return None
        results = [
            block.get("content", "")
            for block in message["content"]
            if isinstance(block, dict) and block.get("type") == "tool_result"
        ]
        return results or None

    @staticmethod
    def _latest_user_text(messages: list[dict[str, Any]]) -> str:
        for message in reversed(messages):
            if message.get("role") == "user" and isinstance(message.get("content"), str):
                return message["content"]
        return ""

    @staticmethod
    def _summarize(tool_results: list[str]) -> str:
        count = 0
        for raw in tool_results:
            try:
                data = json.loads(raw)
                if isinstance(data, list):
                    count += len(data)
            except (json.JSONDecodeError, TypeError):
                pass
        return (
            f"Based on the evidence I gathered ({count} device record(s)), everything I can see "
            "is reporting normally. Tell me which device to look at in detail and I'll dig deeper."
        )


def get_provider() -> LLMProvider:
    settings = get_settings()
    if settings.anthropic_api_key:
        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=settings.ai_model,
            max_tokens=settings.ai_max_tokens,
        )
    return StubProvider()
