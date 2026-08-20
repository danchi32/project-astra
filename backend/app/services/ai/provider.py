"""LLM provider abstraction for the ASTRA cognitive engine.

The engine is a provider-agnostic agentic tool-use loop. `AnthropicProvider` calls
Claude via the official SDK; `StubProvider` is deterministic and lets the platform
run in tests and local demos without an API key or network access.
"""
import json
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Protocol

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# The system prompt is either plain text or a list of content blocks. Blocks exist so the
# stable part of the prompt can carry a cache breakpoint while the per-device sentence
# that follows it stays outside the cached prefix.
SystemPrompt = str | list[dict[str, Any]]


def system_text(system: SystemPrompt) -> str:
    """The system prompt as one string, whichever shape it arrived in.

    Only the built-in providers need this: they read the acting hostname back out of the
    prompt, and there is no reason for each of them to learn the block format.
    """
    if isinstance(system, str):
        return system
    return "\n\n".join(
        str(block.get("text", "")) for block in system if isinstance(block, dict)
    )


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
        self, *, system: SystemPrompt, messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        """Given the system prompt, conversation messages (Anthropic wire format),
        and tool schemas, return the assistant's next turn."""
        ...


#: When Anthropic last rejected our credentials, as a UTC ISO string, or None.
#:
#: Module-level and per process, which is enough for what it is for. The production key
#: was rejected on every call for weeks and nothing said so: /health reported the key was
#: CONFIGURED, which it was, and the assistants degraded politely to "the AI service is
#: temporarily unavailable" — a sentence that reads like a blip, not like an outage. The
#: only trace was a stack trace in the logs nobody had reason to read. So the fact is
#: recorded where a health check can see it.
_last_auth_error: str | None = None


def last_auth_error() -> str | None:
    return _last_auth_error


class AnthropicProvider:
    """Calls Claude via the official Anthropic SDK."""

    def __init__(self, api_key: str, model: str, max_tokens: int) -> None:
        # Imported lazily so the package is only required when a key is configured.
        import anthropic

        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    async def generate(
        self, *, system: SystemPrompt, messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        import anthropic

        # The support chatbot has no tools at all, and the API rejects an empty list
        # rather than reading it as "none" — so the parameter is omitted in that case.
        extra = {"tools": tools} if tools else {}
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system,
                messages=messages,
                **extra,
            )
        except anthropic.AuthenticationError:
            # Distinct from every other failure: nothing retries its way out of a revoked
            # key, and no caller can degrade around it. Recorded, said loudly once here,
            # and re-raised for the caller to handle as it always did.
            global _last_auth_error
            from app.models.base import utcnow

            _last_auth_error = utcnow().isoformat()
            logger.error(
                "Anthropic rejected the API key — every AI feature is down until "
                "ASTRA_ANTHROPIC_API_KEY is replaced with a valid key"
            )
            raise
        # A tool-use turn re-sends the whole brief and every tool schema on each pass of the
        # loop, so the same few thousand tokens are billed three to five times per
        # conversation unless they are cached. Whether they actually were is not something
        # to assume — it is a number the response reports, and a silent cache miss looks
        # exactly like a cache hit from the outside. So it gets logged.
        usage = getattr(response, "usage", None)
        if usage is not None:
            logger.info(
                "claude call model=%s input=%s cache_write=%s cache_read=%s output=%s",
                self._model,
                getattr(usage, "input_tokens", None),
                getattr(usage, "cache_creation_input_tokens", None),
                getattr(usage, "cache_read_input_tokens", None),
                getattr(usage, "output_tokens", None),
            )
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, input=dict(block.input)))
        return LLMResponse(text="".join(text_parts), tool_calls=tool_calls)


@lru_cache(maxsize=256)
def _word_start_matcher(phrases: tuple[str, ...]) -> re.Pattern[str]:
    """Compile keyword phrases so each only matches at the START of a word.

    These lists used to be tested with a plain `phrase in text`, which matched inside
    unrelated words. "hang" is inside "c-hang-e" and "ex-chang-e"; "ram" is inside
    "prog-ram", "diag-ram" and "pa-ram-eter". So "change my timezone", "change my
    password" and "my Exchange mailbox is full" were all read as problem reports, the
    built-in rules answered them with a cleanup, and — because can_handle() gates
    routing — the message never reached the LLM at all. A user asking to change their
    time zone was told their cache had been cleared.

    Anchored only at the START, not at both ends: several entries are stems on purpose.
    "khul" has to reach "khulta", "freez" has to reach "freezing". Requiring a boundary
    at the end too would silently drop those.
    """
    alternatives = "|".join(re.escape(p.strip()) for p in phrases if p.strip())
    return re.compile(rf"\b(?:{alternatives})", re.IGNORECASE)


def mentions(text: str, phrases: tuple[str, ...]) -> bool:
    """Whether `text` uses any of `phrases` as a word (or as the start of one)."""
    return bool(_word_start_matcher(tuple(phrases)).search(text))


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
        # More English phrasings.
        "unresponsive", "not loading", "won't load", "wont load", "keeps freezing",
        "keeps hanging", "black screen", "greyed out", "grayed out", "not opening up",
        "failed to start", "can't open", "cant open", "cannot open", "isn't working",
        "isnt working", "doesn't work", "doesnt work", "does not work", "acting up",
        "glitching", "no response", "won't respond", "wont respond", "quit unexpectedly",
        "closed itself", "keeps restarting", "won't close", "wont close", "not printing",
        "keeps loading", "loading forever", "spinning", "white screen",
        # Hinglish / Hindi
        "nahi", "nhi", " nai", "band", "khul", "chal nahi", "kaam nahi", "kaam ni",
        "dikkat", "kharab", "atak", "ruk", "hang ho", "close ho", "khulta",
        "kaam nhi", "chal nhi", "ho raha", "ho rha", "kar raha",
        "khul nahi", "khul nhi", "khulta nahi", "chal nahi raha", "chal nhi raha",
        "kaam nahi kar raha", "kaam nahi karta", "atak gaya", "ruk gaya",
        "band ho gaya", "band ho raha", "close ho gaya", "hang kar raha",
        "reply nahi", "response nahi", "open nahi ho", "kharab ho gaya",
        "slow ho gaya", "load nahi ho", "khul nahi raha",
    )
    # Connectivity complaints -> a safe automatic network fix (flush DNS or reset
    # the adapter). Matched only alongside a clear problem/loading/connection word.
    _NETWORK_TRIGGERS = (
        "internet", "wifi", "wi-fi", "network", "dns", "website", "websites",
        "web page", "webpage", "no connection", "can't connect", "cant connect",
        "cannot connect", "no internet", "offline",
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
        "brave": ("restart_application", "brave"),
        "acrobat": ("restart_application", "Acrobat"),
        "adobe acrobat": ("restart_application", "Acrobat"),
        "adobe reader": ("restart_application", "AcroRd32"),
        "onedrive": ("restart_application", "onedrive"),
        "one drive": ("restart_application", "onedrive"),
        "whatsapp": ("restart_application", "WhatsApp"),
        "spotify": ("restart_application", "Spotify"),
        "discord": ("restart_application", "Discord"),
        "vs code": ("restart_application", "Code"),
        "vscode": ("restart_application", "Code"),
        "visual studio code": ("restart_application", "Code"),
        "ms access": ("restart_application", "MSACCESS"),
        "microsoft access": ("restart_application", "MSACCESS"),
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
        self, *, system: SystemPrompt, messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
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
        if mentions(user_text, self._KB_TRIGGERS):
            return LLMResponse(
                text="Let me check our knowledge base for that.",
                tool_calls=[ToolCall(
                    id="stub-kb", name="search_knowledge_base", input={"query": user_text},
                )],
            )

        # "change my timezone to IST" → set it. Handled here rather than left to the LLM
        # because it is a common, unambiguous request and the built-in path is the only one
        # a Basic (non-AI-Pro) organization has.
        zone = self._match_timezone_change(user_text)
        if zone is not None:
            return LLMResponse(
                text=f"Sure — setting this PC's time zone to {zone}. The clock corrects itself "
                     "straight away.",
                tool_calls=[ToolCall(
                    id="stub-timezone", name="propose_remediation",
                    input={
                        "action_id": "set_timezone",
                        "timezone_id": zone,
                        "reason": "User asked to change the time zone.",
                    },
                )],
            )

        # A RECURRING Office failure → repair the install. Checked before the app-restart
        # rule below, which would otherwise answer "Outlook keeps crashing" by relaunching
        # it for the third time.
        office_app = self._match_office_repair(user_text)
        if office_app is not None:
            return LLMResponse(
                text=f"{office_app} failing repeatedly usually means the Office installation "
                     "itself is damaged, which a restart won't fix. I've asked your IT team to "
                     "approve a repair — it closes every Office app while it runs, so save your "
                     "work. You'll see it start once they approve.",
                tool_calls=[ToolCall(
                    id="stub-office-repair", name="propose_remediation",
                    input={
                        "action_id": "office_repair",
                        "reason": f"User reports {office_app} failing repeatedly; "
                                  "restarting it has not resolved it.",
                    },
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

        # A connectivity complaint → a safe automatic network fix (flush DNS or
        # reset the adapter).
        net_fix = self._match_network_fix(user_text)
        if net_fix is not None:
            action_id, said = net_fix
            return LLMResponse(
                text=said,
                tool_calls=[ToolCall(
                    id="stub-net-fix", name="propose_remediation",
                    input={"action_id": action_id, "reason": "User reports a connectivity problem."},
                )],
            )

        if mentions(user_text, self._DIAGNOSTIC_KEYWORDS):
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
        if hostname and mentions(user_text, self._PROBLEM_WORDS):
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
        if self._match_office_repair(text) is not None:
            return True
        if self._match_timezone_change(text) is not None:
            return True
        if self._match_explicit_cleanup(text) is not None:
            return True
        if self._match_app_fix(text) is not None:
            return True
        if self._match_network_fix(text) is not None:
            return True
        if mentions(text, self._DIAGNOSTIC_KEYWORDS):
            return True
        if hostname and mentions(text, self._PROBLEM_WORDS):
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
        if not mentions(text, self._PROBLEM_WORDS):
            return None
        for app, (action_id, process_name) in self._APP_ACTIONS.items():
            if mentions(text, (app,)):
                return (app.title(), action_id, process_name)
        return None

    def _match_network_fix(self, text: str) -> tuple[str, str] | None:
        """A connectivity complaint → a safe automatic network fix. Returns
        (action_id, what to say), or None if it isn't clearly a network problem."""
        if not mentions(text, self._NETWORK_TRIGGERS):
            return None
        # Require an actual problem signal, so "what's my wifi name" isn't a fix.
        if not (
            mentions(text, self._PROBLEM_WORDS)
            # "disconnect" is listed separately: anchoring at the word start means
            # "connect" no longer reaches it, and a dropped link is the clearest
            # network complaint there is.
            or mentions(text, ("load", "connect", "disconnect", "down"))
        ):
            return None
        # A dropped/disconnected link → reset the adapter; otherwise treat it as
        # names-not-resolving → flush DNS (the least-disruptive first fix).
        if mentions(text, ("wifi", "wi-fi", "adapter", "disconnect", "dropped",
                           "no connection", "no internet")):
            return ("restart_network_adapter",
                    "Let me reset your network adapter to restore the connection — doing that now.")
        return ("flush_dns",
                "Let me flush the DNS cache so websites load properly — doing that now.")

    # Spoken names -> the Windows identifier tzutil actually wants. People say "IST" and
    # "change me to New York time"; Windows only accepts "India Standard Time". Every value
    # here must exist in SAFE_TIMEZONES, which a test enforces — an id that fails validation
    # server-side would turn a working request into an error the user cannot act on.
    _TIMEZONE_ALIASES: dict[str, str] = {
        "ist": "India Standard Time", "india": "India Standard Time",
        "kolkata": "India Standard Time", "calcutta": "India Standard Time",
        "delhi": "India Standard Time", "mumbai": "India Standard Time",
        "bengaluru": "India Standard Time", "bangalore": "India Standard Time",
        "est": "Eastern Standard Time", "eastern": "Eastern Standard Time",
        "new york": "Eastern Standard Time", "edt": "Eastern Standard Time",
        "cst": "Central Standard Time", "chicago": "Central Standard Time",
        "mst": "Mountain Standard Time", "mountain": "Mountain Standard Time",
        "denver": "Mountain Standard Time",
        "pst": "Pacific Standard Time", "pacific": "Pacific Standard Time",
        "pdt": "Pacific Standard Time", "los angeles": "Pacific Standard Time",
        "california": "Pacific Standard Time", "san francisco": "Pacific Standard Time",
        "seattle": "Pacific Standard Time",
        "atlantic": "Atlantic Standard Time",
        "alaska": "Alaskan Standard Time", "hawaii": "Hawaiian Standard Time",
        "utc": "UTC", "gmt": "GMT Standard Time", "london": "GMT Standard Time",
        "uk": "GMT Standard Time", "bst": "GMT Standard Time",
        "cet": "W. Europe Standard Time", "berlin": "W. Europe Standard Time",
        "amsterdam": "W. Europe Standard Time", "germany": "W. Europe Standard Time",
        "paris": "Romance Standard Time", "madrid": "Romance Standard Time",
        "central europe": "Central Europe Standard Time",
        "eastern europe": "E. Europe Standard Time",
        "moscow": "Russian Standard Time", "turkey": "Turkey Standard Time",
        "istanbul": "Turkey Standard Time", "israel": "Israel Standard Time",
        "dubai": "Arabian Standard Time", "gst": "Arabian Standard Time",
        "uae": "Arabian Standard Time", "riyadh": "Arab Standard Time",
        "pkt": "Pakistan Standard Time", "pakistan": "Pakistan Standard Time",
        "karachi": "Pakistan Standard Time",
        "dhaka": "Bangladesh Standard Time", "bangladesh": "Bangladesh Standard Time",
        "colombo": "Sri Lanka Standard Time", "sri lanka": "Sri Lanka Standard Time",
        "nepal": "Nepal Standard Time", "kathmandu": "Nepal Standard Time",
        "singapore": "Singapore Standard Time", "sgt": "Singapore Standard Time",
        "bangkok": "SE Asia Standard Time", "jakarta": "SE Asia Standard Time",
        "manila": "SE Asia Standard Time", "vietnam": "SE Asia Standard Time",
        "china": "China Standard Time", "beijing": "China Standard Time",
        "shanghai": "China Standard Time", "hong kong": "China Standard Time",
        "jst": "Tokyo Standard Time", "japan": "Tokyo Standard Time",
        "tokyo": "Tokyo Standard Time",
        "kst": "Korea Standard Time", "korea": "Korea Standard Time",
        "seoul": "Korea Standard Time",
        "aest": "AUS Eastern Standard Time", "sydney": "AUS Eastern Standard Time",
        "melbourne": "AUS Eastern Standard Time", "perth": "W. Australia Standard Time",
        "darwin": "AUS Central Standard Time",
        "auckland": "New Zealand Standard Time", "new zealand": "New Zealand Standard Time",
        "johannesburg": "South Africa Standard Time",
        "south africa": "South Africa Standard Time",
        "nairobi": "E. Africa Standard Time", "lagos": "W. Central Africa Standard Time",
        "sao paulo": "E. South America Standard Time",
        "brazil": "E. South America Standard Time",
        "argentina": "Argentina Standard Time", "buenos aires": "Argentina Standard Time",
        "mexico": "Central Standard Time (Mexico)",
        "toronto": "Eastern Standard Time", "vancouver": "Pacific Standard Time",
    }

    _TIMEZONE_WORDS = ("timezone", "time zone", "time-zone", "tz")
    _TIMEZONE_VERBS = ("change", "set", "switch", "update", "correct", "move", "badal", "kar do")

    # Office apps by the names people use for them. "word" is the loose one — it is an
    # ordinary English word — but a repair signal is required as well, and the action is
    # approval-gated, so a stray match costs a declined approval rather than a repair.
    _OFFICE_APPS = (
        "outlook", "winword", "excel", "powerpoint", "powerpnt", "onenote",
        "ms word", "microsoft word", "ms excel", "microsoft excel", "word",
        "microsoft office", "ms office", "office 365", "microsoft 365", "o365", "office",
    )
    # What separates "restart it" from "repair it": RECURRENCE. A single hang is cleared by
    # relaunching the app, which is instant and costs nothing; repetition is what says the
    # install itself is damaged, and a repair force-closes every Office app to fix it.
    #
    # Two independent axes rather than whole phrases. The first attempt listed exact
    # wordings — "keeps crashing" — and a user who wrote "outlook keep crashing" got a
    # restart, because "keeps crashing" does not match "keep crashing". People write this a
    # dozen ways; requiring one word from each list covers them without trying to enumerate
    # the combinations. Word-start matching does the rest: "keep" reaches keeps/keeping,
    # "crash" reaches crashes/crashing.
    _RECURRENCE_WORDS = (
        "keep", "again", "every time", "each time", "everytime", "repeated", "repeatedly",
        "over and over", "still", "constantly", "always", "frequently", "multiple times",
        "second time", "third time",
        # Hinglish — how these actually arrive.
        "bar bar", "baar baar", "har baar", "hamesha", "roz", "phir se", "dobara", "fir se",
    )
    _FAILURE_WORDS = (
        "crash", "clos", "freez", "hang", "restart", "not respond", "unresponsive",
        "quit", "stuck", "shut down", "shutting down", "band", "error",
    )
    # Enough on their own: these name the remedy, or the cause a repair addresses.
    _EXPLICIT_REPAIR_WORDS = ("repair", "corrupt", "reinstall", "damaged", "broken install")

    def _match_office_repair(self, text: str) -> str | None:
        """A recurring Office failure → repair the install. Returns the app to name, or None.

        Deliberately NOT triggered by a one-off complaint: "Outlook won't open" is answered
        by restarting Outlook, which is immediate and disruptive to nobody. Repair is the
        answer to "it keeps happening", and it is approval-gated because it force-closes
        every Office app and takes unsaved work with them.
        """
        if not mentions(text, self._OFFICE_APPS):
            return None
        explicit = mentions(text, self._EXPLICIT_REPAIR_WORDS)
        recurring = mentions(text, self._RECURRENCE_WORDS) and mentions(text, self._FAILURE_WORDS)
        if not (explicit or recurring):
            return None

        for alias, label in (
            ("outlook", "Outlook"), ("excel", "Excel"), ("powerpoint", "PowerPoint"),
            ("powerpnt", "PowerPoint"), ("onenote", "OneNote"), ("winword", "Word"),
            ("word", "Word"),
        ):
            if mentions(text, (alias,)):
                return label
        return "Microsoft Office"

    def _match_timezone_change(self, text: str) -> str | None:
        """A request to change the time zone → the Windows identifier to set, or None.

        Requires the words "time zone" AND a change verb. A bare "IST" or a message that
        merely mentions New York must not silently repoint someone's clock — and moving a
        time zone moves every appointment in their calendar with it.

        Picking the TARGET is the subtle part: "change from EST to IST" names two zones, and
        acting on the first would set exactly the one they are trying to leave. Anything
        after the last "to" wins; otherwise the last one named does.
        """
        if not mentions(text, self._TIMEZONE_WORDS):
            return None
        if not mentions(text, self._TIMEZONE_VERBS):
            return None

        # Longest alias first: "central europe" must beat the "central" inside it.
        aliases = sorted(self._TIMEZONE_ALIASES, key=len, reverse=True)
        pattern = re.compile(rf"\b(?:{'|'.join(re.escape(a) for a in aliases)})\b")
        found = [(m.start(), self._TIMEZONE_ALIASES[m.group(0)]) for m in pattern.finditer(text)]
        if not found:
            return None

        marker = text.rfind(" to ")
        if marker != -1:
            after = [tz for pos, tz in found if pos > marker]
            if after:
                return after[0]
        return found[-1][1]

    def _match_explicit_cleanup(self, text: str) -> tuple[str, str] | None:
        """Direct cleanup requests → (action_id, what to say). All safe/automatic and
        never touch user data (browser cache = HTTP cache only, not history/passwords)."""
        cleanup_verb = mentions(text, ("clear", "clean", "delete", "flush", "free up", "wipe"))
        wants_cache = mentions(text, ("cache",))
        wants_browser = mentions(text, self._BROWSER_WORDS)
        wants_temp = mentions(text, ("temp", "temporary", "junk"))

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

    def _acting_hostname(self, system: SystemPrompt) -> str | None:
        match = self._HOSTNAME_RE.search(system_text(system))
        return match.group(1) if match else None

    def _follow_up_after_evidence(
        self, tool_results: list[str], complaint: str
    ) -> LLMResponse | None:
        """After gathering telemetry for a vague "it's slow" complaint, take the safe
        automatic action (clear temp files) rather than just reporting numbers back."""
        if not mentions(complaint, self._PERF_WORDS):
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
                if mentions(complaint, self._BROWSER_WORDS):
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
                # Clean BOTH temp locations. clear_temp only reaches the signed-in user's
                # %TEMP%; the machine-wide C:\Windows\Temp needs the elevated service via
                # clear_system_temp, and on a long-lived device that is usually where the
                # bulk of the reclaimable space sits. Both are AUTOMATIC-tier and
                # self-rebuilding, so proposing them together is safe.
                # The ids must differ — identical ids would collapse into one dispatch.
                return LLMResponse(
                    text=(
                        f"Your system is at {cpu}% CPU and {ram}% memory right now. "
                        "I'll clear out temporary files — both yours and the machine-wide "
                        "ones — to free up space and help it run smoother."
                    ),
                    tool_calls=[
                        ToolCall(
                            id="stub-cleanup-user", name="propose_remediation",
                            input={
                                "action_id": "clear_temp",
                                "reason": "User reports the device is slow; clearing temp files.",
                            },
                        ),
                        ToolCall(
                            id="stub-cleanup-system", name="propose_remediation",
                            input={
                                "action_id": "clear_system_temp",
                                "reason": (
                                    "User reports the device is slow; clearing the machine-wide "
                                    "Windows temp folder."
                                ),
                            },
                        ),
                    ],
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


class LearnedActionProvider:
    """Applies a fix the AI learned for a previously-unclassified issue — no LLM
    call. Drives the same engine loop as the stub: propose the remembered action,
    then summarize the outcome from the tool result."""

    def __init__(self, action_id: str, params: dict[str, Any] | None) -> None:
        self._action_id = action_id
        self._params = params or {}

    async def generate(
        self, *, system: SystemPrompt, messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        results = StubProvider._extract_tool_results(messages[-1])
        if results is not None:
            return LLMResponse(text=StubProvider._summarize(results))
        tool_input: dict[str, Any] = {
            "action_id": self._action_id,
            "reason": "Applying the known fix for this kind of issue.",
        }
        tool_input.update(self._params)
        return LLMResponse(
            text="I've handled this kind of issue before — applying the known fix now.",
            tool_calls=[ToolCall(id="learned", name="propose_remediation", input=tool_input)],
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
