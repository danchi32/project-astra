"""Cheap intent gate: cheaply reject clearly off-topic queries before any LLM call.

Fail-open by design — when unsure, allow the query through rather than block a
real IT problem. Its only job is to catch obvious "use me like ChatGPT" misuse
(poems, recipes, trivia) so those never reach the paid model.
"""

# Signals that a message is a genuine IT / device support request.
_IT_KEYWORDS = (
    "computer", "laptop", "pc", "device", "machine", "desktop", "workstation",
    "slow", "freeze", "frozen", "freezing", "crash", "hang", "stuck", "lag",
    "restart", "reboot", "not working", "won't", "wont", "not open", "not opening",
    "not responding", "error", "blue screen", "bsod",
    "outlook", "teams", "zoom", "email", "mail", "office", "word", "excel",
    "onedrive", "sharepoint", "browser", "chrome", "edge",
    "wifi", "wi-fi", "internet", "network", "vpn", "connect", "connection",
    "printer", "print", "scan",
    "password", "login", "log in", "sign in", "account", "locked out",
    "install", "update", "driver", "software", "application", "app", "program",
    "disk", "storage", "space", "memory", "ram", "cpu", "battery",
    "keyboard", "mouse", "screen", "monitor", "display", "audio", "sound", "mic",
    "microphone", "camera", "bluetooth", "usb", "file", "folder", "access",
    "virus", "malware", "security", "slow computer", "fix", "help",
)

# Clear markers of a non-IT, general-assistant request.
_OFF_TOPIC_MARKERS = (
    "poem", "write a story", "short story", "recipe", "cook", "joke",
    "capital of", "who won", "who is the", "translate", "translation",
    "essay", "lyrics", "song about", "horoscope", "meaning of life",
    "workout", "diet plan", "stock", "bitcoin", "crypto price", "weather",
    "movie recommendation", "book recommendation", "tell me about history",
    "homework", "math problem", "solve this equation",
)

OFF_TOPIC_REPLY = (
    "I'm ASTRA, your IT assistant — I can only help with computer, device, and "
    "IT issues (things like a frozen app, no internet, printer trouble, or a "
    "password reset). For anything else, please use a general assistant. Is there "
    "a device or IT problem I can help you with?"
)


def is_off_topic(text: str) -> bool:
    """True only when the message is clearly non-IT. Fail-open otherwise."""
    lowered = text.lower()
    if any(kw in lowered for kw in _IT_KEYWORDS):
        return False
    if any(marker in lowered for marker in _OFF_TOPIC_MARKERS):
        return True
    return False


# An app the assistant can act on, or a word signalling a problem/cleanup request.
# When present, the message needs the live engine (it may perform a fix) — so the
# semantic cache must NOT serve or store it, or a cached text answer would shadow the
# action. Includes Hinglish/Hindi markers, since end users chat that way.
_ACTIONABLE_APPS = (
    "outlook", "teams", "zoom", "chrome", "edge", "firefox", "brave", "word", "excel",
    "powerpoint", "onenote", "slack", "skype", "notepad", "explorer", "taskbar",
    "acrobat", "adobe", "browser",
)
_ACTIONABLE_MARKERS = (
    "crash", "frozen", "freeze", "freezing", "not responding", "hang", "hung", "stuck",
    "fix", "restart", "won't open", "wont open", "not open", "not opening", "not working",
    "not launching", "not starting", "won't start", "wont start", "broken", "keeps closing",
    "keeps crashing", "error", "issue", "problem", "slow", "lag", "stopped",
    "clear", "clean", "cache", "temp", "flush", "dns",
    # Hinglish / Hindi
    "nahi", "nhi", "band", "khul", "kaam nahi", "kaam nhi", "dikkat", "kharab", "atak",
    "ruk", "chal nahi", "chal nhi", "ho raha", "ho rha",
)


# "What you did made no difference." Distinct from _PROBLEM_WORDS on purpose: those say
# *a* problem exists, these say *this* problem survived a fix — which is the sentence that
# moves a conversation to the next tier. Meaningless on its own, so the caller must also
# establish that something was actually tried; otherwise the first message of a chat that
# happens to say "still not working" would escalate before ASTRA had lifted a finger.
_STILL_BROKEN = (
    "still not", "still cant", "still can't", "still doesn't", "still does not",
    "still isnt", "still isn't", "still the same", "still same", "still happening",
    "still crashing", "still slow", "still there", "still an issue", "still broken",
    "same problem", "same issue", "same thing", "no change", "no difference",
    "didn't work", "didnt work", "did not work", "doesn't help", "does not help",
    "didn't help", "didnt help", "not fixed", "wasn't fixed", "hasn't fixed",
    "nothing changed", "no luck", "tried that", "already tried",
    # Hinglish / Hindi
    "abhi bhi", "abhi b", "ab bhi", "phir se", "fir se", "wahi problem", "wahi dikkat",
    "wahi issue", "koi fark nahi", "koi farak nahi", "fark nahi pada", "thik nahi hua",
    "theek nahi hua", "sahi nahi hua", "nahi hua", "nhi hua", "kaam nahi aaya",
    "kaam nhi aaya", "same hai", "waise ka waisa",
)


def reports_still_broken(text: str) -> bool:
    """True when the user is saying the previous attempt did not help."""
    lowered = text.lower()
    return any(marker in lowered for marker in _STILL_BROKEN)


def requires_live_action(text: str) -> bool:
    """True when the message names an app or reports a problem/cleanup — such messages
    must reach the engine live and bypass the semantic cache entirely."""
    lowered = text.lower()
    return any(a in lowered for a in _ACTIONABLE_APPS) or any(
        m in lowered for m in _ACTIONABLE_MARKERS
    )
