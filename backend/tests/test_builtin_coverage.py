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


def test_sound_complaints_rebuild_the_audio_stack():
    for msg in [
        "no sound on my laptop", "my mic is not working", "microphone not working",
        "headset stopped working", "speakers not working", "can't hear anyone on calls",
        "audio nahi aa raha", "awaaz nahi aa rahi",
    ]:
        assert s._match_audio_fix(msg) == "restart_audio", msg
        assert s.can_handle(user_text=msg, hostname="PC-1"), msg


def test_audio_words_do_not_swallow_the_app_the_user_named():
    """mentions() matches at a word START — deliberately, so "freez" reaches "freezing".
    Applied to the audio vocabulary that turns three of the commonest words in an IT
    complaint into a sound problem:

        mic   -> MICrosoft            hear  -> HEARd
        sound -> SOUNDs like

    Each of these would have rebuilt the audio stack instead of restarting the app the user
    actually named, and can_handle() would have kept the message away from the LLM too."""
    for msg, expected_app in [
        ("microsoft teams not working", "restart_teams"),
        ("it sounds like teams is not working", "restart_teams"),
        ("sounds like outlook crashed again", "restart_outlook"),
        ("i heard chrome is broken", "restart_chrome"),
    ]:
        assert s._match_audio_fix(msg) is None, msg
        assert s._match_app_fix(msg)[1] == expected_app, msg

    # ...while the real complaints still match.
    for msg in ["my mic is dead", "there is no sound", "i can't hear anyone",
                "sound stopped working"]:
        assert s._match_audio_fix(msg) == "restart_audio", msg


def test_asking_about_audio_is_not_a_fix():
    for msg in ["which headset am I using", "how do I change my speakers"]:
        assert s._match_audio_fix(msg) is None, msg


def test_undetected_hardware_triggers_a_rescan():
    for msg in [
        "my headset is not detected", "second monitor not showing up",
        "usb device not recognized", "the docking station is not detected",
        "webcam not detected", "pen drive detect nahi ho raha",
    ]:
        assert s._match_hardware_rescan(msg) == "rescan_devices", msg
        assert s.can_handle(user_text=msg, hostname="PC-1"), msg


async def test_a_rescan_beats_the_audio_rule_when_both_match():
    """A missing endpoint is not fixed by bouncing the audio service, so when the message
    says both "no sound" and "not detected", the rescan has to be the one that runs."""
    msg = "no sound at all, my headset is not detected"
    assert s._match_hardware_rescan(msg) == "rescan_devices"
    assert s._match_audio_fix(msg) == "restart_audio"        # both fire...
    reply = await s.generate(
        system="", messages=[{"role": "user", "content": msg}], tools=[])
    assert reply.tool_calls[0].input["action_id"] == "rescan_devices"   # ...rescan wins


def test_a_device_fault_is_not_a_rescan():
    """A rescan finds hardware Windows cannot see. A device it can see but that misbehaves
    is a different problem, and a rescan does nothing for it."""
    assert s._match_hardware_rescan("my monitor is flickering") is None
    assert s._match_hardware_rescan("how do I connect a second monitor") is None
