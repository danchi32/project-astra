"""Phase 3 · D10 browser policy: stored per org behind the ai_guard add-on, served to its PCs,
and their reports kept, with tampering raised to the admin."""
from sqlalchemy import select

from app.models import AuditLog, Notification, Organization, UserRole


async def _guard_on(session_factory, org_id, on=True):
    async with session_factory() as s:
        org = await s.get(Organization, org_id)
        org.entitlement_overrides = {**(org.entitlement_overrides or {}), "ai_guard": on}
        await s.commit()


async def _enroll(client, admin_headers, host="GUARD-1"):
    key = (await client.get("/api/v1/devices/installer", headers=admin_headers)).json()["enrollment_key"]
    r = (await client.post("/api/v1/agent/enroll", json={
        "enrollment_token": key, "hostname": host, "machine_id": host.lower(),
        "os_version": "Windows 11", "agent_version": "0.16.0"})).json()
    return r["device_id"], {"Authorization": f"Bearer {r['device_token']}"}


POLICY = {"incognito_off": True, "extension_developer_mode_off": True,
          "blocked_sites": ["https://Example.com/", "files.example.org", "example.com"],
          "google_allowed_domains": ["acme.in"]}


async def test_without_the_add_on_nothing_is_served(client, admin_headers, session_factory, admin_user):
    assert (await client.get("/api/v1/guard/browser-policy", headers=admin_headers)).status_code == 402
    _, h = await _enroll(client, admin_headers)
    assert (await client.get("/api/v1/agent/browser-policy", headers=h)).json() == {"version": 0, "policy": {}}


async def test_admin_sets_it_pcs_get_it(client, admin_headers, session_factory, admin_user):
    await _guard_on(session_factory, admin_user.org_id)
    r = await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json=POLICY)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["version"] == 1
    assert body["policy"]["blocked_sites"] == ["example.com", "files.example.org"]   # normalised, deduped

    # The same policy again is not a new version; a change is.
    assert (await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json=POLICY)).json()["version"] == 1
    v2 = await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json={**POLICY, "dev_tools_off": True})
    assert v2.json()["version"] == 2

    _, h = await _enroll(client, admin_headers)
    served = (await client.get("/api/v1/agent/browser-policy", headers=h)).json()
    assert served["version"] == 2 and served["policy"]["dev_tools_off"] is True

    # Turning the add-on off serves an empty policy, so PCs remove what SAVIO set.
    await _guard_on(session_factory, admin_user.org_id, on=False)
    assert (await client.get("/api/v1/agent/browser-policy", headers=h)).json() == {"version": 0, "policy": {}}

    async with session_factory() as s:
        audits = (await s.execute(select(AuditLog).where(AuditLog.action == "guard.browser_policy_update"))).scalars().all()
    assert len(audits) == 3 and "dev_tools_off" in audits[-1].detail["changed"]


async def test_bad_policies_are_refused(client, admin_headers, session_factory, admin_user):
    await _guard_on(session_factory, admin_user.org_id)
    for bad in ({"blocked_sites": ["not a host"]}, {"chrome_extension_id": "xyz"},
                {"firefox_extension_id": "savio@savio.app"},
                {"firefox_extension_id": "savio@savio.app", "firefox_extension_url": "http://x.in/a.xpi"},
                {"blocked_sites": [f"s{i}.example.com" for i in range(501)]},
                # Review L2 / L4: unknown fields refused, invisible text in keywords refused, and a
                # forced Firefox extension only from Mozilla's store.
                {"incognito_off": True, "made_up": 1}, {"guard_keywords": ["fal\u202econ"]},
                {"firefox_extension_id": "savio@savio.app", "firefox_extension_url": "https://evil.example/x.xpi"}):
        r = await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json=bad)
        assert r.status_code == 422, (bad, r.text)


async def test_extension_settings(client, admin_headers, session_factory, admin_user):
    """D3: the extension's own settings ride on the same policy. Keywords are config the admin
    typed; the audit names the fields that changed, never the keywords themselves."""
    await _guard_on(session_factory, admin_user.org_id)
    r = await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json=POLICY)
    assert r.json()["policy"]["guard_mode"] == "log" and r.json()["policy"]["guard_ignore_kinds"] == ["Email"]
    await client.post("/api/v1/guard/browser-policy/end-pilot", headers=admin_headers)   # E8

    body = {**POLICY, "guard_mode": "warn", "guard_watched_sites": ["https://ChatGPT.com/"],
            "guard_ignore_kinds": ["Email", "Email", "IndianMobile"],
            "guard_keywords": [" project falcon ", "Project Falcon", "Q3 numbers"]}
    p = (await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json=body)).json()["policy"]
    assert p["guard_watched_sites"] == ["chatgpt.com"]
    assert p["guard_ignore_kinds"] == ["Email", "IndianMobile"]
    assert p["guard_keywords"] == ["project falcon", "Q3 numbers"]

    async with session_factory() as s:
        audit = (await s.execute(select(AuditLog).where(AuditLog.action == "guard.browser_policy_update")
                                 .order_by(AuditLog.created_at.desc()))).scalars().first()
    assert "guard_keywords" in audit.detail["changed"] and "falcon" not in str(audit.detail)

    for bad in ({"guard_mode": "shout"}, {"guard_ignore_kinds": ["Passwords"]}, {"guard_keywords": ["  "]},
                {"guard_keywords": ["x" * 101]}, {"guard_keywords": [f"k{i}" for i in range(201)]},
                {"guard_watched_sites": ["not a host"]}):
        assert (await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json=bad)).status_code == 422, bad


async def test_blocking_by_category(client, admin_headers, session_factory, admin_user):
    """D1: a category is served to PCs as its hosts, merged into the one block list. The hosts are
    copied when saved, so a list changed in a later release reaches PCs only with a new version."""
    from app.models import OrgBrowserPolicy
    from app.services import browser_policy

    await _guard_on(session_factory, admin_user.org_id)
    cats = (await client.get("/api/v1/guard/site-categories", headers=admin_headers)).json()
    assert {c["key"] for c in cats} == set(browser_policy.SITE_CATEGORIES)
    assert "wetransfer.com" in next(c for c in cats if c["key"] == "file_sharing")["hosts"]

    body = {"blocked_sites": ["example.com", "wetransfer.com"], "blocked_categories": ["file_sharing", "file_sharing"],
            "allowed_sites": ["we.tl"]}
    r = (await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json=body)).json()
    assert r["policy"]["blocked_categories"] == ["file_sharing"] and r["policy"]["blocked_sites"] == ["example.com", "wetransfer.com"]
    _, h = await _enroll(client, admin_headers)
    served = (await client.get("/api/v1/agent/browser-policy", headers=h)).json()
    sites = served["policy"]["blocked_sites"]
    assert sites[:2] == ["example.com", "wetransfer.com"] and "mega.nz" in sites and len(sites) == len(set(sites))
    assert "blocked_categories" not in served["policy"] and served["policy"]["allowed_sites"] == ["we.tl"]

    # A release changes the list: saving the same policy picks it up as a new version.
    async with session_factory() as s:
        row = await s.get(OrgBrowserPolicy, admin_user.org_id)
        row.category_hosts = ["wetransfer.com"]
        await s.commit()
    assert "mega.nz" not in (await client.get("/api/v1/agent/browser-policy", headers=h)).json()["policy"]["blocked_sites"]
    again = (await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json=body)).json()
    assert again["version"] == 2
    assert "mega.nz" in (await client.get("/api/v1/agent/browser-policy", headers=h)).json()["policy"]["blocked_sites"]

    too_many = {"blocked_sites": [f"s{i}.example.com" for i in range(495)], "blocked_categories": ["file_sharing"]}
    assert (await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json=too_many)).status_code == 422
    assert (await client.put("/api/v1/guard/browser-policy", headers=admin_headers,
                             json={"blocked_categories": ["gambling"]})).status_code == 422


async def test_a_new_org_only_records_for_14_days(client, admin_headers, user_headers, session_factory, admin_user):
    """E8: the pilot. Nothing but record-only until it ends, by the date or by an admin (audited);
    it never switches a mode on by itself."""
    from datetime import datetime, timedelta

    from app.models import OrgBrowserPolicy
    from app.models.base import as_utc, utcnow

    await _guard_on(session_factory, admin_user.org_id)
    url = "/api/v1/guard/browser-policy"
    fresh = (await client.get(url, headers=admin_headers)).json()
    assert fresh["version"] == 0 and fresh["pilot_until"] is not None          # it starts with the first save
    assert (await client.put(url, headers=admin_headers, json={**POLICY, "guard_mode": "warn"})).status_code == 409

    r = (await client.put(url, headers=admin_headers, json=POLICY)).json()
    left = datetime.fromisoformat(r["pilot_until"]) - utcnow()
    assert timedelta(days=13, hours=23) < left <= timedelta(days=14)
    refused = await client.put(url, headers=admin_headers, json={**POLICY, "guard_mode": "block"})
    assert refused.status_code == 409 and "End the pilot" in refused.json()["detail"]
    _, h = await _enroll(client, admin_headers)
    assert (await client.get("/api/v1/agent/browser-policy", headers=h)).json()["policy"]["guard_mode"] == "log"

    async def set_until(when):
        async with session_factory() as s:
            row = await s.get(OrgBrowserPolicy, admin_user.org_id)
            row.pilot_until = when
            await s.commit()

    await set_until(utcnow() - timedelta(minutes=1))                          # 14 days later
    assert (await client.get(url, headers=admin_headers)).json()["pilot_until"] is None
    assert (await client.get(url, headers=admin_headers)).json()["policy"]["guard_mode"] == "log"   # nothing switched on
    assert (await client.put(url, headers=admin_headers, json={**POLICY, "guard_mode": "warn"})).status_code == 200
    assert (await client.post(f"{url}/end-pilot", headers=admin_headers)).status_code == 404

    await set_until(utcnow() + timedelta(days=3))                             # ending it early
    assert (await client.post(f"{url}/end-pilot", headers=user_headers)).status_code == 403
    ended = await client.post(f"{url}/end-pilot", headers=admin_headers)
    assert ended.status_code == 200 and ended.json()["pilot_until"] is None
    async with session_factory() as s:
        audit = (await s.execute(select(AuditLog).where(AuditLog.action == "guard.pilot_end"))).scalars().one()
        assert as_utc((await s.get(OrgBrowserPolicy, admin_user.org_id)).pilot_until) <= utcnow()
    assert audit.actor_id == admin_user.id


async def test_manual_install(client, admin_headers, session_factory, admin_user):
    """A hand-installed extension (pilot before the store listing, or testing): no install URL,
    and developer mode must stay available for it."""
    await _guard_on(session_factory, admin_user.org_id)
    ok = {"chrome_extension_id": "abcdefghijklmnopabcdefghijklmnop", "firefox_extension_id": "guard@savio.app",
          "extension_install": "manual"}
    r = await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json=ok)
    assert r.status_code == 200 and r.json()["policy"]["extension_install"] == "manual"
    for bad in ({**ok, "extension_developer_mode_off": True},
                {**ok, "firefox_extension_url": "https://addons.mozilla.org/x.xpi"},
                {**ok, "extension_install": "sideload"}):
        assert (await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json=bad)).status_code == 422, bad


async def test_roles(client, admin_headers, user_headers, session_factory, admin_user, org):
    from tests.conftest import _create_user, auth_headers

    await _guard_on(session_factory, admin_user.org_id)
    await _create_user(session_factory, org.id, "tech@acme.com", "TechPassw0rd!2345", UserRole.TECHNICIAN)
    tech = await auth_headers(client, "tech@acme.com", "TechPassw0rd!2345")
    await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json={**POLICY, "guard_keywords": ["project falcon"]})
    seen = await client.get("/api/v1/guard/browser-policy", headers=tech)
    assert seen.status_code == 200 and seen.json()["policy"]["guard_keywords"] == []     # review L1: admins only
    assert (await client.get("/api/v1/guard/browser-policy", headers=admin_headers)).json()["policy"]["guard_keywords"] == ["project falcon"]
    assert (await client.put("/api/v1/guard/browser-policy", headers=tech, json=POLICY)).status_code == 403
    assert (await client.get("/api/v1/guard/browser-policy", headers=user_headers)).status_code == 403


async def test_reports_are_kept_and_tampering_is_raised(client, admin_headers, session_factory, admin_user):
    await _guard_on(session_factory, admin_user.org_id)
    await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json=POLICY)
    _, h = await _enroll(client, admin_headers, "TAMPER-PC")

    clean = {"version": 1, "results": [
        {"browser": "Chrome", "set": ["IncognitoModeAvailability"], "conflicts": ["URLBlocklist"]},
        {"browser": "Firefox", "error": "Existing policies.json is not valid JSON, left untouched"}]}
    assert (await client.post("/api/v1/agent/browser-policy/report", headers=h, json=clean)).status_code == 204
    states = (await client.get("/api/v1/guard/browser-policy/devices", headers=admin_headers)).json()
    assert states[0]["hostname"] == "TAMPER-PC" and states[0]["results"][0]["conflicts"] == ["URLBlocklist"]

    tampered = {"version": 1, "results": [{"browser": "Chrome", "repaired": ["IncognitoModeAvailability"]}]}
    await client.post("/api/v1/agent/browser-policy/report", headers=h, json=tampered)
    async with session_factory() as s:
        note = (await s.execute(select(Notification).where(Notification.title == "Browser policy tampered"))).scalars().one()
        audit = (await s.execute(select(AuditLog).where(AuditLog.action == "guard.browser_policy_tamper"))).scalars().one()
    assert "TAMPER-PC" in note.message and audit.detail["repaired"] == ["Chrome: IncognitoModeAvailability"]
    assert len((await client.get("/api/v1/guard/browser-policy/devices", headers=admin_headers)).json()) == 1

    # The admin changed the policy: the first report of version 2 rewrites values, an update.
    # A planted user-level host in the same report is still tampering.
    updated = {"version": 2, "results": [{"browser": "Chrome", "repaired": [
        "IncognitoModeAvailability", "user-level com.savio.guard"]}]}
    await client.post("/api/v1/agent/browser-policy/report", headers=h, json=updated)
    async with session_factory() as s:
        audits = (await s.execute(select(AuditLog).where(AuditLog.action == "guard.browser_policy_tamper")
                                  .order_by(AuditLog.created_at))).scalars().all()
    assert [a.detail["repaired"] for a in audits][1:] == [["Chrome: user-level com.savio.guard"]]
    chrome = (await client.get("/api/v1/guard/browser-policy/devices", headers=admin_headers)).json()[0]["results"][0]
    assert chrome["set"] == ["IncognitoModeAvailability"] and chrome["repaired"] == ["user-level com.savio.guard"]

    # E4: the scanner's firewall block reports beside the browsers, and its problems show.
    scanner = {"version": 1, "results": [{"browser": "Scanner", "error": "Windows Firewall is off for at least one profile"}]}
    assert (await client.post("/api/v1/agent/browser-policy/report", headers=h, json=scanner)).status_code == 204
    states = (await client.get("/api/v1/guard/browser-policy/devices", headers=admin_headers)).json()
    assert states[0]["results"][0]["browser"] == "Scanner"

    bogus = {"version": 1, "results": [{"browser": "Opera"}]}
    assert (await client.post("/api/v1/agent/browser-policy/report", headers=h, json=bogus)).status_code == 422


async def test_tamper_reports_cannot_carry_prose_or_flood(client, admin_headers, session_factory, admin_user):
    """Review M1: report names are policy names, never a sentence, and a PC raises at most one
    tamper notification an hour (the audit keeps every one)."""
    await _guard_on(session_factory, admin_user.org_id)
    _, h = await _enroll(client, admin_headers, "LOOP-PC")
    await client.post("/api/v1/agent/browser-policy/report", headers=h, json={"version": 1, "results": []})
    for _ in range(3):
        r = {"version": 1, "results": [{"browser": "Chrome", "repaired": [
            "IncognitoModeAvailability", "Your account is locked! Call +1-555-0100 now", "\u202eevil"]}]}
        await client.post("/api/v1/agent/browser-policy/report", headers=h, json=r)
    async with session_factory() as s:
        notes = (await s.execute(select(Notification).where(Notification.title == "Browser policy tampered"))).scalars().all()
        audits = (await s.execute(select(AuditLog).where(AuditLog.action == "guard.browser_policy_tamper"))).scalars().all()
    assert len(notes) == 1 and len(audits) == 3
    assert "locked" not in notes[0].message and "\u202e" not in notes[0].message


async def test_reports_from_an_org_without_the_add_on_are_dropped(client, admin_headers, session_factory, admin_user):
    _, h = await _enroll(client, admin_headers)
    r = {"version": 1, "results": [{"browser": "Chrome", "repaired": ["IncognitoModeAvailability"]}]}
    assert (await client.post("/api/v1/agent/browser-policy/report", headers=h, json=r)).status_code == 204
    async with session_factory() as s:
        assert (await s.execute(select(Notification))).scalars().first() is None
