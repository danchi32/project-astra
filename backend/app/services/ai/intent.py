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
