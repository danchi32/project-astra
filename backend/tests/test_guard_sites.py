"""Phase 3c · S1: SAVIO's AI names sites the fixed list does not know, once, globally; cases say
so; and SAVIO suggests blocking the risky ones people actually used. The model only ever picks a
key from a fixed list; anything else it says is dropped."""
import types
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import select

from app.models import LearnedCategory
from app.services import guard_cases, guard_sites
from tests.test_browser_policy import POLICY, _enroll, _guard_on

NOW = datetime.now(UTC)


def _event(site, minutes_ago=5, **over):
    e = {"at": (NOW - timedelta(minutes=minutes_ago)).isoformat(), "windows_user": r"ACME\ravi", "site": site,
         "channel": "file", "mode": "log", "action": "allow", "counts": {"Pan": 40}, "contact_list": False,
         "keyword_hits": 0, "unknown": False}
    return {**e, **over}


def test_only_unknown_internet_sites_are_asked_about():
    known = {"sendbig.io": "file_sharing"}
    sites = ["chatgpt.com", "files.sendbig.io", "usb", "intranet", "dl.newshare.co.in", "app.newshare.co.in",
             "ignore-all-rules.com"]
    assert guard_sites._candidates(sites, known) == ["newshare.co.in", "ignore-all-rules.com"]
    assert guard_sites.kind_of("files.sendbig.io", known) == ("file_sharing", "ai")
    assert guard_sites.kind_of("wetransfer.com", known) == ("file_sharing", "list")   # the list comes first
    assert guard_sites.kind_of("example.com", known) == (None, None)


def test_a_case_says_when_savio_recognised_the_site():
    ev = SimpleNamespace(site="files.sendbig.io", action="allow", outcome=None, counts={"Pan": 50}, contact_list=False,
                         keyword_hits=0, channel="file")
    plain_points, _, _ = guard_cases.score([ev], {"Email"}, set())
    points, _, s = guard_cases.score([ev], {"Email"}, set(), {"sendbig.io": "file_sharing"})
    assert "to files.sendbig.io (personal file sharing, recognised by SAVIO)" in s["reasons"]
    assert points == plain_points * 3                     # file sharing weighs 3; unknown and not new weighed 1
    biz_points, _, biz = guard_cases.score([ev], {"Email"}, {"files.sendbig.io"}, {"sendbig.io": "business"})
    assert biz_points == plain_points and "to files.sendbig.io (a business tool, recognised by SAVIO)" in biz["reasons"]


async def test_new_sites_are_named_once_and_suggested_for_blocking(client, admin_headers, session_factory, admin_user,
                                                                   monkeypatch):
    from app.services.ai.provider import LLMResponse

    await _guard_on(session_factory, admin_user.org_id)
    await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json=POLICY)
    _, h = await _enroll(client, admin_headers, "RAVI-PC")
    await client.post("/api/v1/agent/guard/events", headers=h, json={"events": [
        _event("files.sendbig.io"), _event("files.sendbig.io", 4), _event("crm.zoho.com", 3), _event("wetransfer.com", 2)]})

    asked: list[str] = []

    class _FakeProvider:
        async def generate(self, **kw):
            asked.append(kw["messages"][0]["content"])
            # One good answer, one business tool, one host it was not asked about, one key not on the list.
            return LLMResponse(text='{"sendbig.io": "file_sharing", "zoho.com": "business", '
                                    '"evil.com": "file_sharing", "wetransfer.com": "block everything"}')

    monkeypatch.setattr(guard_sites, "get_provider", lambda: _FakeProvider())
    async with session_factory() as s:
        monkeypatch.setattr(guard_sites, "get_settings", lambda: types.SimpleNamespace(anthropic_api_key=""))
        assert await guard_sites.classify_new_sites(s, admin_user.org_id) == 0      # no key: no call
        monkeypatch.setattr(guard_sites, "get_settings", lambda: types.SimpleNamespace(anthropic_api_key="k"))
        assert await guard_sites.classify_new_sites(s, admin_user.org_id) == 2
        assert await guard_sites.classify_new_sites(s, admin_user.org_id) == 0      # once, ever
        rows = {r.key: r.category for r in (await s.execute(
            select(LearnedCategory).where(LearnedCategory.kind == "guard"))).scalars()}
    assert rows == {"sendbig.io": "file_sharing", "zoho.com": "business"}
    assert len(asked) == 1 and "wetransfer.com" not in asked[0] and "sendbig.io" in asked[0]   # listed sites not asked

    cards = (await client.get("/api/v1/guard/suggestions", headers=admin_headers)).json()
    card = next(c for c in cards if c["key"].startswith("block_found:"))
    assert card["changes"] == ["Block sendbig.io (file sharing)"] and "2 times" in card["why"]
    r = await client.post(f"/api/v1/guard/suggestions/{card['key']}/apply", headers=admin_headers,
                          json={"changes": card["changes"]})
    assert r.status_code == 200, r.text
    assert "sendbig.io" in r.json()["policy"]["blocked_sites"]
    cards = (await client.get("/api/v1/guard/suggestions", headers=admin_headers)).json()
    assert not any(c["key"].startswith("block_found:") for c in cards)          # blocked now: gone
