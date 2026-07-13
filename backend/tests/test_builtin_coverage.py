"""The built-in rules keep more issues in the free tier: more apps, more phrasings
(English + Hinglish), and connectivity fixes — while genuinely unlisted questions
still route to the LLM."""
from app.services.ai.provider import StubProvider

s = StubProvider()


def test_more_apps_recognised():
    for msg in [
        "onedrive not working", "whatsapp crashed", "spotify won't open",
        "discord not responding", "vs code frozen", "brave not opening",
        "ms access not working", "adobe acrobat hung",
    ]:
        assert s._match_app_fix(msg) is not None, msg
        assert s.can_handle(user_text=msg, hostname="PC-1"), msg


def test_more_phrasings_stay_free():
    for msg in [
        "teams is unresponsive", "my excel keeps freezing", "outlook won't respond",
        "word closed itself", "the printer is not printing", "chrome doesn't work",
        # Hinglish
        "outlook khul nahi raha", "teams band ho gaya", "excel load nahi ho raha",
    ]:
        assert s.can_handle(user_text=msg, hostname="PC-1"), msg


def test_connectivity_fixes():
    assert s._match_network_fix("my wifi keeps disconnecting")[0] == "restart_network_adapter"
    assert s._match_network_fix("no internet connection")[0] == "restart_network_adapter"
    assert s._match_network_fix("websites won't load")[0] == "flush_dns"
    assert s._match_network_fix("dns not working, pages not loading")[0] == "flush_dns"
    assert s.can_handle(user_text="websites won't load", hostname="PC-1")
    # An informational question is NOT a fix.
    assert s._match_network_fix("what is my wifi password") is None


def test_unlisted_issues_still_route_to_llm():
    for msg in [
        "explain our vpn split-tunneling policy",
        "summarise the asset depreciation schedule",
        "my badge reader won't sync with the door",
    ]:
        assert not s.can_handle(user_text=msg, hostname="PC-1"), msg
