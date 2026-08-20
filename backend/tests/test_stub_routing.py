"""Which messages the built-in rules claim, and which they must hand to the LLM.

`can_handle` is a routing gate, not a hint: when it returns True the built-in rules
answer and Claude never sees the message. So a keyword that fires too eagerly does not
merely produce a clumsy reply — it silently replaces the reasoning engine.

That is what happened. The lists were tested with a plain `phrase in text`, and "hang"
lives inside "c-hang-e" and "ex-chang-e" while "ram" lives inside "prog-ram",
"diag-ram" and "pa-ram-eter". A user who asked to change their time zone was told their
cache had been cleared, because "change" read as a hang, the hang read as a performance
problem, and the performance path runs a cleanup.

Both halves are pinned here. Narrowing the match is only correct if genuine problem
reports still route to the rules, so the second half is as load-bearing as the first.
"""
import pytest

from app.services.ai.provider import StubProvider, mentions

HOST = "LSI-1322"


@pytest.fixture
def stub():
    return StubProvider()


@pytest.mark.parametrize("message", [
    # NOTE: "change my timezone to IST" is deliberately absent. It was the message that
    # exposed this bug, but the rules now handle it properly with set_timezone — see the
    # time-zone tests below. What matters is that it is no longer answered with a cleanup,
    # not that it reaches the LLM.
    "can you change the default printer",
    "change my password",
    # "Exchange" is an email system — every mention of it was reading as a hang.
    "my Exchange mailbox is full",
    "how do I connect to Exchange online",
    # "ram" inside ordinary words sent these down the diagnostics path.
    "please add a program to my laptop",
    "I need a diagram tool installed",
    "what is the parameter for this setting",
])
def test_ordinary_requests_are_left_to_the_llm(stub, message):
    assert stub.can_handle(user_text=message.lower(), hostname=HOST) is False, (
        f"{message!r} was claimed by the built-in rules, so Claude never sees it."
    )


@pytest.mark.parametrize("message", [
    "outlook keeps crashing",
    "excel is not responding",
    "my laptop is very slow",
    "app freezing constantly",
    "clear my browser cache",
    "delete temporary files",
    "check my RAM usage",
    "wifi disconnect ho raha hai",
    # Hinglish, which is how end users actually write.
    "teams nahi khul raha",
    "chrome hang ho raha hai",
    "khulta nahi hai",
])
def test_real_problem_reports_still_route_to_the_rules(stub, message):
    assert stub.can_handle(user_text=message.lower(), hostname=HOST) is True, (
        f"{message!r} stopped matching — narrowing the keywords went too far."
    )


def test_a_timezone_request_is_not_answered_with_a_cleanup(stub):
    """The exact user-visible symptom, rather than only the routing behind it."""
    text = "change timezone from est to ist"
    assert stub._match_explicit_cleanup(text) is None
    assert stub._follow_up_after_evidence(["cpu 12%"], text) is None


def test_keywords_match_word_starts_but_not_word_interiors():
    assert mentions("the app keeps hanging", ("hang",))
    assert not mentions("change my settings", ("hang",))
    assert not mentions("exchange server", ("hang",))

    assert mentions("ram usage is high", ("ram",))
    assert not mentions("open the program", ("ram",))


def test_stem_entries_still_reach_their_longer_forms():
    """Several entries are deliberately stems. Anchoring at both ends would have
    dropped them, and the loss would only have shown up as the assistant quietly
    ignoring Hinglish."""
    assert mentions("it keeps freezing", ("freez",))
    assert mentions("file khulta nahi", ("khul",))
    assert mentions("atakta hai", ("atak",))


def test_disconnect_still_reads_as_a_network_problem():
    """'connect' anchored at a word start no longer reaches 'disconnect', so it is
    listed in its own right — a dropped link is the clearest network complaint there is."""
    assert stub_network("my wifi keeps disconnecting") == "restart_network_adapter"


def stub_network(message: str) -> str | None:
    match = StubProvider()._match_network_fix(message.lower())
    return match[0] if match else None


# ── Changing the time zone without an LLM ──────────────────────────────────
#
# A Basic organization has no Claude, so whatever the built-in rules cannot do, the
# product cannot do for them. Changing a time zone is common enough, and unambiguous
# enough, to belong here rather than behind the AI-Pro entitlement.


@pytest.mark.parametrize("message,expected", [
    # The target is the zone being moved TO. Acting on the first one named would set
    # exactly the zone the user is trying to leave.
    ("change timezone from IST to EST", "Eastern Standard Time"),
    ("change timezone from EST to IST", "India Standard Time"),
    ("set my time zone to India Standard Time", "India Standard Time"),
    ("please change my timezone to new york", "Eastern Standard Time"),
    ("update time zone to Tokyo", "Tokyo Standard Time"),
    # Longest alias wins: "central europe" must beat the "central" inside it.
    ("switch timezone to central europe", "Central Europe Standard Time"),
    # Hinglish, which is how these actually arrive.
    ("timezone badal do IST me", "India Standard Time"),
])
def test_a_timezone_request_resolves_to_the_windows_identifier(stub, message, expected):
    assert stub._match_timezone_change(message.lower()) == expected


@pytest.mark.parametrize("message", [
    "what timezone am I in",             # a question, not an instruction
    "I am flying to new york tomorrow",  # a place, with no intent to change anything
    "IST",                               # a bare zone name is not a request
    "outlook keeps crashing",
])
def test_the_clock_is_not_moved_without_being_asked(stub, message):
    """Moving a time zone moves every appointment in the person's calendar with it, so
    merely mentioning a place must never be enough to trigger it."""
    assert stub._match_timezone_change(message.lower()) is None


def test_every_alias_resolves_to_a_zone_the_server_will_accept(stub):
    """These ids go straight to _validate_timezone, which rejects anything outside
    SAFE_TIMEZONES. An alias pointing at a zone that fails there would turn a request
    the rules understood into an error the user can do nothing about."""
    from app.services.remediation.actions import SAFE_TIMEZONES

    unknown = sorted(
        f"{alias} -> {zone}"
        for alias, zone in stub._TIMEZONE_ALIASES.items()
        if zone not in SAFE_TIMEZONES
    )
    assert not unknown, f"aliases pointing outside SAFE_TIMEZONES: {unknown}"


async def test_the_rules_propose_set_timezone_with_the_resolved_id(stub):
    """End of the built-in path: the right action, carrying the right parameter."""
    response = await stub.generate(
        system="You are ASTRA, acting for the logged-in user of device 'LSI-1322'.",
        messages=[{"role": "user", "content": "change timezone from EST to IST"}],
        tools=[],
    )
    call = next(c for c in response.tool_calls if c.name == "propose_remediation")
    assert call.input["action_id"] == "set_timezone"
    assert call.input["timezone_id"] == "India Standard Time"


# ── Repairing Office, without an LLM ───────────────────────────────────────
#
# The built-in rules could not propose office_repair at all: "outlook keeps crashing"
# restarted Outlook and "repair office" matched nothing whatsoever. So on a Basic plan
# the fix for a damaged Office install was unreachable however the user phrased it.


@pytest.mark.parametrize("message,app", [
    # "keep", not "keeps". The first version of this rule listed whole phrases, so a user
    # who wrote "outlook keep crashing" got a restart — the exact wording decided whether
    # the feature existed. Recurrence and failure are matched as separate words now.
    ("outlook keep crashing", "Outlook"),
    ("outlook keeps on crashing", "Outlook"),
    ("word keeps closing again and again", "Word"),
    ("excel crashes every time I open it", "Excel"),
    ("powerpoint hangs constantly", "PowerPoint"),
    ("outlook crashed 3 times today, always same error", "Outlook"),
    ("outlook keeps crashing", "Outlook"),
    ("MS Word keeps closing", "Word"),
    ("powerpoint crashes every time", "PowerPoint"),
    ("outlook still crashing after restart", "Outlook"),
    ("my office install is corrupted", "Microsoft Office"),
    # Asked for by name.
    ("repair office", "Microsoft Office"),
    # Hinglish, which is how these actually arrive.
    ("excel bar bar band ho rahi hai", "Excel"),
    ("onenote har baar band ho jata hai", "OneNote"),
])
def test_a_recurring_office_failure_proposes_a_repair(stub, message, app):
    assert stub._match_office_repair(message.lower()) == app


@pytest.mark.parametrize("message,expected_restart", [
    ("outlook won't open", "restart_outlook"),
    # A crash reported ONCE is still a restart — recurrence is the whole distinction.
    ("outlook crashed", "restart_outlook"),
    ("excel is not responding", "restart_application"),
    ("word is frozen", "restart_application"),
])
def test_a_one_off_office_problem_still_just_restarts_the_app(stub, message, expected_restart):
    """Recurrence is what separates the two. Relaunching an app is instant and disruptive to
    nobody; an Office repair force-closes every Office app and takes minutes. Answering a
    single hang with a repair would cost someone their unsaved work to fix nothing."""
    assert stub._match_office_repair(message.lower()) is None
    assert stub._match_app_fix(message.lower())[1] == expected_restart


@pytest.mark.parametrize("message", [
    # "word" is an ordinary English word; requiring a repair signal as well is what keeps
    # it from firing on ordinary sentences.
    "in other words my wifi keeps dropping",
    "how do I install office",
    "change my timezone to IST",
    # "keep" is a recurrence word, but nothing here is failing.
    "keep the excel file in my folder",
])
def test_the_repair_does_not_fire_on_ordinary_mentions(stub, message):
    assert stub._match_office_repair(message.lower()) is None


async def test_the_repair_is_proposed_for_approval_and_warns_about_open_apps(stub):
    """It stays approval-gated on purpose, and the reply has to say why the wait exists —
    and that work will be lost when it does run."""
    response = await stub.generate(
        system="You are ASTRA, acting for the logged-in user of device 'LSI-1322'.",
        messages=[{"role": "user", "content": "outlook keeps crashing"}],
        tools=[],
    )
    call = next(c for c in response.tool_calls if c.name == "propose_remediation")
    assert call.input["action_id"] == "office_repair"
    assert "approve" in response.text.lower()
    assert "save your work" in response.text.lower()
