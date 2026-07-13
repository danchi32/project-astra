"""LLM provider abstraction for the ASTRA cognitive engine.

The engine is a provider-agnostic agentic tool-use loop. `AnthropicProvider` calls
Claude via the official SDK; `StubProvider` is deterministic and lets the platform
run in tests and local demos without an API key or network access.
"""
import json
import re
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
    # Signals that a message is a problem report rather than a how-to. Includes common
    # Hinglish/Hindi markers, since end users often chat that way ("teams nahi khul raha").
    _PROBLEM_WORDS = (
        "crash", "frozen", "freeze", "freezing", "not responding", "hang", "hung",
        "stuck", "fix", "restart", "won't open", "wont open", "keeps closing",
        "not open", "not opening", "not working", "not launching", "not starting",
        "won't start", "wont start", "broken", "keeps closing", "keeps crashing",
        "error", "issue", "problem", "slow", "lag", "stopped",
        # Hinglish / Hindi
        "nahi", "nhi", " nai", "band", "khul", "chal nahi", "kaam nahi", "kaam ni",
        "dikkat", "kharab", "atak", "ruk", "hang ho", "close ho", "khulta",
        "kaam nhi", "chal nhi", "ho raha", "ho rha", "kar raha",
    )
    # Apps the assistant can restart. Value is (action_id, process_name). A None
    # process_name means there's a dedicated action; otherwise the generic
    # restart_application action is used with that process name.
    _APP_ACTIONS: dict[str, tuple[str, str | None]] = {
        "outlook": ("restart_outlook", None),
        "teams": ("restart_teams", None),
        "zoom": ("restart_zoom", None),
        "chrome": ("restart_chrome", None),
        "edge": ("restart_edge", None),
        "explorer": ("restart_explorer", None),
        "taskbar": ("restart_explorer", None),
        "file explorer": ("restart_explorer", None),
        # Generic restarts (kill + relaunch by process name).
        "word": ("restart_application", "WINWORD"),
        "excel": ("restart_application", "EXCEL"),
        "powerpoint": ("restart_application", "POWERPNT"),
        "onenote": ("restart_application", "ONENOTE"),
        "slack": ("restart_application", "slack"),
        "skype": ("restart_application", "Skype"),
        "notepad": ("restart_application", "notepad"),
        "firefox": ("restart_application", "firefox"),
        "acrobat": ("restart_application", "Acrobat"),
        "adobe reader": ("restart_application", "AcroRd32"),
    }
    _KB_TRIGGERS = (
        "how do i", "how to", "how can i", "how do you", "steps to", "guide",
        "set up", "setup", "configure", "connect to", "where do i", "where can i",
    )
    _GREETINGS = ("hi", "hello", "hey", "hii", "hola", "yo", "namaste", "thanks", "thank you",
                  "thankyou", "ok", "okay", "cool", "great")
    # A vague "my machine is slow/laggy" — no specific app — where clearing temp
    # files is the safe, automatic first-line tune-up after checking telemetry.
    _PERF_WORDS = ("slow", "laggy", "lag", "sluggish", "performance", "freez", "hang")
    _BROWSER_WORDS = ("browser", "chrome", "edge", "firefox", "brave", "website", "web page",
                      "webpage", "page", "internet")

    # The engine embeds the acting device's hostname in the system prompt for a
    # tray chat: "... the logged-in user of device 'HOST' ...". Pull it back out so
    # the stub scopes its evidence-gathering to THAT device, not the whole fleet.
    _HOSTNAME_RE = re.compile(r"device '([^']+)'")

    async def generate(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        last = messages[-1]
        hostname = self._acting_hostname(system)

        # If we just received tool results, decide whether to act on the evidence
        # or summarize and finish.
        tool_results = self._extract_tool_results(last)
        if tool_results is not None:
            complaint = self._latest_user_text(messages).lower()
            follow_up = self._follow_up_after_evidence(tool_results, complaint)
            if follow_up is not None:
                return follow_up
            return LLMResponse(text=self._summarize(tool_results, hostname))

        # Otherwise inspect the latest user text.
        user_text = self._latest_user_text(messages).lower()

        # A bare greeting → greet back (don't spin up diagnostics for "hi"/"thanks").
        if self._is_greeting(user_text):
            return LLMResponse(
                text=(
                    "Hi! I'm ASTRA, your IT assistant. Tell me what's going wrong — for example "
                    "\"Teams won't open\", \"my system is slow\", or \"clear my browser cache\" — "
                    "and I'll fix it for you."
                )
            )

        # A how-to / knowledge question → search the knowledge base (checked before app
        # matching, so "how to set up Teams" searches docs rather than restarting Teams).
        if any(trigger in user_text for trigger in self._KB_TRIGGERS):
            return LLMResponse(
                text="Let me check our knowledge base for that.",
                tool_calls=[ToolCall(
                    id="stub-kb", name="search_knowledge_base", input={"query": user_text},
                )],
            )

        # A direct "clear my cache / clean temp files" request → the matching safe action.
        cleanup = self._match_explicit_cleanup(user_text)
        if cleanup is not None:
            action_id, said = cleanup
            return LLMResponse(
                text=said,
                tool_calls=[ToolCall(
                    id="stub-cleanup-direct", name="propose_remediation",
                    input={"action_id": action_id, "reason": "User asked for this cleanup."},
                )],
            )

        # An app the user named is misbehaving → restart it (dedicated action for the
        # common apps, generic kill-and-relaunch for the rest).
        app_fix = self._match_app_fix(user_text)
        if app_fix is not None:
            app_name, action_id, process_name = app_fix
            tool_input: dict[str, Any] = {
                "action_id": action_id,
                "reason": f"User reports {app_name} is not working; restarting it.",
            }
            if process_name is not None:
                tool_input["process_name"] = process_name
            return LLMResponse(
                text=f"Let me restart {app_name} for you — doing that now.",
                tool_calls=[ToolCall(
                    id="stub-app-fix", name="propose_remediation", input=tool_input,
                )],
            )

        if any(kw in user_text for kw in self._DIAGNOSTIC_KEYWORDS):
            # In a tray chat we know exactly whose device this is — inspect that one
            # device's telemetry rather than listing the whole organization.
            if hostname:
                return LLMResponse(
                    text=f"Let me check what's going on with {hostname} before I answer.",
                    tool_calls=[ToolCall(
                        id="stub-telemetry", name="get_device_telemetry",
                        input={"hostname": hostname},
                    )],
                )
            return LLMResponse(
                text="Let me gather the current device telemetry before answering.",
                tool_calls=[ToolCall(id="stub-tool-1", name="list_devices", input={})],
            )

        # A problem report that didn't name a specific app → gather evidence on this
        # device before answering, instead of dead-ending.
        if hostname and any(w in user_text for w in self._PROBLEM_WORDS):
            return LLMResponse(
                text="Let me take a look at your device to see what's going on.",
                tool_calls=[ToolCall(
                    id="stub-telemetry", name="get_device_telemetry",
                    input={"hostname": hostname},
                )],
            )

        # Otherwise it's a general / device-independent question → a stable text answer
        # (no tools), which the semantic cache can serve for free next time.
        return LLMResponse(
            text=(
                "I'm ASTRA, your IT assistant. I can fix common problems for you — for example "
                "restarting an app that won't open, clearing temporary files or browser cache, "
                "or flushing DNS when websites won't load. Tell me what's going wrong and I'll "
                "take care of it."
            )
        )

    def can_handle(self, *, user_text: str, hostname: str | None) -> bool:
        """True when the message matches a listed/common issue the built-in rules
        resolve on their own — an app restart, a cleanup, a device diagnostic, or a
        greeting. Used to route: only when this is False (an unusual, unlisted
        problem) is the LLM (Claude) worth spending. Mirrors the matching in
        generate(); knowledge-base how-to questions are intentionally left to the
        LLM when one is configured."""
        text = user_text.lower()
        if self._is_greeting(text):
            return True
        if self._match_explicit_cleanup(text) is not None:
            return True
        if self._match_app_fix(text) is not None:
            return True
        if any(kw in text for kw in self._DIAGNOSTIC_KEYWORDS):
            return True
        if hostname and any(w in text for w in self._PROBLEM_WORDS):
            return True
        return False

    def _is_greeting(self, text: str) -> bool:
        stripped = text.strip().strip("!.? ")
        if stripped in self._GREETINGS:
            return True
        tokens = stripped.split()
        # "hello there", "hi astra" — a greeting word leading a very short message.
        return bool(tokens) and tokens[0] in self._GREETINGS and len(tokens) <= 3

    def _match_app_fix(self, text: str) -> tuple[str, str, str | None] | None:
        """If the user named an app and the message reads like a problem, return
        (app_label, action_id, process_name-or-None)."""
        if not any(w in text for w in self._PROBLEM_WORDS):
            return None
        for app, (action_id, process_name) in self._APP_ACTIONS.items():
            if app in text:
                return (app.title(), action_id, process_name)
        return None

    def _match_explicit_cleanup(self, text: str) -> tuple[str, str] | None:
        """Direct cleanup requests → (action_id, what to say). All safe/automatic and
        never touch user data (browser cache = HTTP cache only, not history/passwords)."""
        cleanup_verb = any(v in text for v in ("clear", "clean", "delete", "flush", "free up", "wipe"))
        wants_cache = "cache" in text
        wants_browser = any(w in text for w in self._BROWSER_WORDS)
        wants_temp = "temp" in text or "temporary" in text or "junk" in text

        if wants_cache and wants_browser:
            return ("clear_browser_cache",
                    "Sure — clearing your browser cache now (this won't touch your history, "
                    "passwords or bookmarks).")
        if cleanup_verb and wants_cache:
            # "clear my cache" with no app named → browser cache is the safe default.
            return ("clear_browser_cache",
                    "Sure — clearing your browser cache now (history, passwords and bookmarks "
                    "are left untouched).")
        if cleanup_verb and wants_temp:
            return ("clear_temp", "On it — clearing out temporary files to free up space.")
        return None

    def _acting_hostname(self, system: str) -> str | None:
        match = self._HOSTNAME_RE.search(system or "")
        return match.group(1) if match else None

    def _follow_up_after_evidence(
        self, tool_results: list[str], complaint: str
    ) -> LLMResponse | None:
        """After gathering telemetry for a vague "it's slow" complaint, take the safe
        automatic action (clear temp files) rather than just reporting numbers back."""
        if not any(w in complaint for w in self._PERF_WORDS):
            return None
        for raw in tool_results:
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            # Only act on real telemetry evidence (never on an error result).
            if isinstance(data, dict) and "cpu_percent" in data:
                cpu = data.get("cpu_percent", 0)
                ram = data.get("ram_percent", 0)
                # If the complaint is browser-specific, the safe first fix is the browser
                # cache; otherwise a general temp-file cleanup.
                if any(w in complaint for w in self._BROWSER_WORDS):
                    return LLMResponse(
                        text=(
                            f"Your system is at {cpu}% CPU and {ram}% memory. Since it's the "
                            "browser that's slow, I'll clear its cache now — your history, "
                            "passwords and bookmarks stay untouched."
                        ),
                        tool_calls=[ToolCall(
                            id="stub-cleanup", name="propose_remediation",
                            input={
                                "action_id": "clear_browser_cache",
                                "reason": "User reports the browser is slow; clearing its cache.",
                            },
                        )],
                    )
                return LLMResponse(
                    text=(
                        f"Your system is at {cpu}% CPU and {ram}% memory right now. "
                        "I'll clear out temporary files to free up space and help it run "
                        "smoother — doing that now."
                    ),
                    tool_calls=[ToolCall(
                        id="stub-cleanup", name="propose_remediation",
                        input={
                            "action_id": "clear_temp",
                            "reason": "User reports the device is slow; clearing temp files.",
                        },
                    )],
                )
        return None

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
    def _summarize(tool_results: list[str], hostname: str | None = None) -> str:
        count = 0
        for raw in tool_results:
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(data, dict) and ("outcome" in data or "task_id" in data):
                outcome = data.get("outcome", "I've applied the fix.")
                return f"Done — {outcome} Anything else?"
            if isinstance(data, dict) and "error" in data:
                error = data["error"]
                return f"I wasn't able to apply that fix: {error}"
            # Knowledge-base search results: {"articles": [{title, content}, ...]}.
            if isinstance(data, dict) and "articles" in data:
                articles = data["articles"]
                if articles:
                    top = articles[0]
                    snippet = str(top.get("content", ""))[:400]
                    return f"From our knowledge base — **{top['title']}**:\n\n{snippet}"
                return (
                    "I couldn't find a relevant article in our knowledge base for that. "
                    "You may want to add one, or tell me more about the problem."
                )
            # Single-device telemetry: {hostname, cpu_percent, ram_percent, disks, ...}.
            if isinstance(data, dict) and "cpu_percent" in data:
                return StubProvider._summarize_telemetry(data)
            if isinstance(data, list):
                count += len(data)
        # Fallback (e.g. a fleet-wide list_devices from the portal, not a tray chat).
        return (
            f"Based on the evidence I gathered ({count} device record(s)), everything I can see "
            "is reporting normally. Tell me which device to look at in detail and I'll dig deeper."
        )

    @staticmethod
    def _summarize_telemetry(data: dict[str, Any]) -> str:
        cpu = data.get("cpu_percent", 0)
        ram = data.get("ram_percent", 0)
        disks = data.get("disks") or []
        disk_line = ""
        for disk in disks:
            total = disk.get("total_gb") or 0
            free = disk.get("free_gb") or 0
            if total:
                disk_line = f" Your {disk.get('drive', 'main')} drive has {free:.0f} GB free of {total:.0f} GB."
                break

        flags = []
        if cpu >= 85:
            flags.append(f"CPU is running hot at {cpu}%")
        if ram >= 85:
            flags.append(f"memory is nearly full at {ram}%")

        health = f"I checked your system: CPU is at {cpu}% and memory at {ram}%.{disk_line}"
        if flags:
            return (
                f"{health} The {' and '.join(flags)} — that's likely what's slowing things down. "
                "Tell me if you'd like me to close heavy background apps or clear temporary files."
            )
        return (
            f"{health} Everything looks healthy right now — nothing is overloaded. "
            "If it still feels slow, tell me what you were doing and I'll dig into the event logs."
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
