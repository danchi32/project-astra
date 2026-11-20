"""Phase 3 · D10 browser policy: stored per org behind the ai_guard add-on, served to its PCs,
and their reports kept, with tampering raised to the admin."""
import uuid

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
    assert p["guard_read_pdfs"] is False                                     # off unless the admin turns it on

    async with session_factory() as s:
        audit = (await s.execute(select(AuditLog).where(AuditLog.action == "guard.browser_policy_update")
                                 .order_by(AuditLog.created_at.desc()))).scalars().first()
    assert "guard_keywords" in audit.detail["changed"] and "falcon" not in str(audit.detail)

    await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json={**body, "guard_read_pdfs": True})
    _, h = await _enroll(client, admin_headers, "PDF-PC")
    assert (await client.get("/api/v1/agent/browser-policy", headers=h)).json()["policy"]["guard_read_pdfs"] is True

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
                             json={"blocked_categories": ["astrology"]})).status_code == 422


async def test_named_policies_follow_the_person(client, admin_headers, user_headers, session_factory, admin_user,
                                                regular_user, other_org_user):
    """Named policies are for teams and users, not machines. A PC gets the winning policy of the
    person it is assigned to in Assets (else the default), so giving that person another PC moves
    their policy with them. Versions are never reused, so a move is always an update."""
    await _guard_on(session_factory, admin_user.org_id)
    a, ha = await _enroll(client, admin_headers, "SALES-1")
    b, hb = await _enroll(client, admin_headers, "SPARE-1")
    url = "/api/v1/guard/policies"
    served = lambda h: client.get("/api/v1/agent/browser-policy", headers=h)

    async def assign(device_id, user_id, name):
        r = await client.post("/api/v1/assets", headers=admin_headers,
                              json={"name": name, "device_id": device_id, "assigned_to_user_id": user_id})
        assert r.status_code == 201, r.text
        return r.json()["id"]

    team = (await client.post("/api/v1/grouping/teams", headers=admin_headers, json={"name": "Sales"})).json()["id"]
    await client.put(f"/api/v1/grouping/teams/{team}/users", headers=admin_headers, json={"user_ids": [str(regular_user.id)]})
    sales = {"name": "Sales", "priority": 5, "team_ids": [team], "policy": {**POLICY, "blocked_categories": ["social_media"]}}

    # New policies start from the default one, so that comes first.
    assert (await client.post(url, headers=admin_headers, json=sales)).status_code == 409
    assert (await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json=POLICY)).json()["version"] == 1

    r = await client.post(url, headers=admin_headers, json=sales)
    assert r.status_code == 201 and r.json()["version"] == 2 and r.json()["team_ids"] == [team]
    sales_id = r.json()["id"]
    assert (await client.post(url, headers=admin_headers, json={**sales, "name": " sales "})).status_code == 409  # name in use
    for bad in ({**sales, "name": "Other", "team_ids": [str(uuid.uuid4())]},
                {**sales, "name": "Other", "user_ids": [str(other_org_user.id)]}):     # not this org's
        assert (await client.post(url, headers=admin_headers, json=bad)).status_code == 404
    assert (await client.post(url, headers=admin_headers,
                              json={**sales, "name": "Loud", "policy": {"guard_mode": "warn"}})).status_code == 409  # E8 pilot
    assert (await client.post(url, headers=user_headers, json={**sales, "name": "X"})).status_code == 403

    # Nobody assigned yet: both PCs are on the default.
    assert (await served(ha)).json()["version"] == 1
    asset = await assign(a, str(regular_user.id), "Laptop A")
    pa = (await served(ha)).json()
    assert pa["version"] == 2 and {"facebook.com"} <= set(pa["policy"]["blocked_sites"])  # by the person's team
    assert (await served(hb)).json()["version"] == 1

    # A policy naming the user directly, ranked higher, wins over the team's.
    me = (await client.post(url, headers=admin_headers, json={
        "name": "Exceptions", "priority": 1, "user_ids": [str(regular_user.id)], "policy": {"dev_tools_off": True}})).json()
    assert me["version"] == 3 and (await served(ha)).json()["version"] == 3

    # The person gets another PC: their policy moves with them; the old PC falls back to the default.
    assert (await client.patch(f"/api/v1/assets/{asset}", headers=admin_headers,
                               json={"device_id": b})).status_code == 200
    assert (await served(hb)).json()["version"] == 3 and (await served(ha)).json()["version"] == 1

    # Re-ranking or reassigning changes who wins without a new version: the version names the content.
    r = await client.put(f"{url}/{me['id']}", headers=admin_headers, json={
        "name": "Exceptions", "priority": 9, "user_ids": [str(regular_user.id)], "policy": {"dev_tools_off": True}})
    assert r.json()["version"] == 3 and (await served(hb)).json()["version"] == 2
    listed = (await client.get(url, headers=admin_headers)).json()
    assert [p["name"] for p in listed] == ["Sales", "Exceptions"]

    # The default changing takes the next number, never one a named policy used.
    assert (await client.put("/api/v1/guard/browser-policy", headers=admin_headers,
                             json={**POLICY, "dev_tools_off": True})).json()["version"] == 4

    # Each PC's row says which policy it should be on, and whose PC it is.
    await client.post("/api/v1/agent/browser-policy/report", headers=hb, json={"version": 2, "results": []})
    rows = {d["hostname"]: d for d in (await client.get("/api/v1/guard/browser-policy/devices", headers=admin_headers)).json()}
    assert rows["SPARE-1"]["policy_name"] == "Sales" and rows["SPARE-1"]["policy_version"] == 2
    assert rows["SPARE-1"]["assigned_to"] == regular_user.full_name

    # Deleting a policy sends its people's PCs back to the default.
    assert (await client.delete(f"{url}/{sales_id}", headers=user_headers)).status_code == 403
    assert (await client.delete(f"{url}/{sales_id}", headers=admin_headers)).status_code == 204
    assert (await served(hb)).json()["version"] == 3
    assert (await client.delete(f"{url}/{sales_id}", headers=admin_headers)).status_code == 404
    async with session_factory() as s:
        actions = [a.action for a in (await s.execute(select(AuditLog).where(
            AuditLog.action.like("guard.named_policy%")))).scalars()]
    assert actions.count("guard.named_policy_update") == 3 and actions.count("guard.named_policy_delete") == 1


async def test_company_accounts_only(client, admin_headers, session_factory, admin_user):
    """D2 beyond Google: the org's own IDs per service, normalised, validated, served to PCs as is.
    They work through the extension, so without one they are refused rather than silently off."""
    await _guard_on(session_factory, admin_user.org_id)
    tid, pid = "AAAABBBB-0000-CCCC-1111-DDDD2222EEEE", "1aaaaaa1-2bb2-3cc3-4dd4-5eeeeeeeeee5"
    body = {"chrome_extension_id": "abcdefghijklmnopabcdefghijklmnop",
            "microsoft_tenant_id": tid, "microsoft_policy_id": pid,
            "claude_org_ids": [" 11111111-2222-4333-8444-555555555555 "],
            "chatgpt_workspace_ids": ["66666666-7777-4888-9999-aaaaaaaaaaaa"],
            "slack_requester_id": "e0123abcd", "slack_allowed_ids": ["E0123ABCD", "t0456efgh", "E0123ABCD"]}
    r = await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json=body)
    assert r.status_code == 200, r.text
    p = r.json()["policy"]
    assert p["microsoft_tenant_id"] == tid.lower() and p["claude_org_ids"] == ["11111111-2222-4333-8444-555555555555"]
    assert p["slack_requester_id"] == "E0123ABCD" and p["slack_allowed_ids"] == ["E0123ABCD", "T0456EFGH"]
    _, h = await _enroll(client, admin_headers)
    served = (await client.get("/api/v1/agent/browser-policy", headers=h)).json()["policy"]
    assert served["microsoft_policy_id"] == pid and served["chatgpt_workspace_ids"] == ["66666666-7777-4888-9999-aaaaaaaaaaaa"]

    for bad in ({**body, "microsoft_policy_id": None},                          # both or neither
                {**body, "slack_allowed_ids": []},
                {**body, "claude_org_ids": ["acme"]},
                {**body, "slack_requester_id": "workspace-1"},
                {**body, "chatgpt_workspace_ids": ["x"] * 51},
                {k: v for k, v in body.items() if k != "chrome_extension_id"},       # needs the extension
                {"microsoft_on_windows": True}):                                      # Windows needs the IDs
        assert (await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json=bad)).status_code == 422, bad

    # Microsoft 365 on the PC itself: Windows enforces the IDs, so no extension is needed for them.
    windows = {"microsoft_tenant_id": tid, "microsoft_policy_id": pid, "microsoft_on_windows": True}
    assert (await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json=windows)).status_code == 200
    served = (await client.get("/api/v1/agent/browser-policy", headers=h)).json()["policy"]
    assert served["microsoft_on_windows"] is True and served["microsoft_tenant_id"] == tid.lower()
    # What the PC reports about it shows beside the browsers, conflicts included.
    report = {"version": 2, "results": [{"browser": "Windows", "conflicts": ["policyid", "tenantid"]}]}
    assert (await client.post("/api/v1/agent/browser-policy/report", headers=h, json=report)).status_code == 204
    state = (await client.get("/api/v1/guard/browser-policy/devices", headers=admin_headers)).json()[0]
    assert state["results"][0] == {"browser": "Windows", "set": [], "repaired": [], "removed": [],
                                   "conflicts": ["policyid", "tenantid"], "error": None}


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


async def test_other_browsers(client, admin_headers, session_factory, admin_user):
    """D10: browsers the policy cannot reach are listed per PC from its app inventory, can be
    closed on start, and each close the PC reports is audited. Only known names are accepted."""
    import uuid

    from app.models import DeviceInstalledApp
    from app.models.base import utcnow

    await _guard_on(session_factory, admin_user.org_id)
    body = (await client.put("/api/v1/guard/browser-policy", headers=admin_headers,
                             json={**POLICY, "block_other_browsers": True})).json()
    assert body["policy"]["block_other_browsers"] is True
    did, h = await _enroll(client, admin_headers, "OPERA-PC")
    assert (await client.get("/api/v1/agent/browser-policy", headers=h)).json()["policy"]["block_other_browsers"] is True

    async with session_factory() as s:
        for name in ("Opera GX Stable 112.0", "Brave", "Operations Manager", "Google Chrome", "Tor Browser"):
            s.add(DeviceInstalledApp(device_id=uuid.UUID(did), org_id=admin_user.org_id, name=name,
                                     collected_at=utcnow()))
        await s.commit()
    report = {"version": 1, "results": [], "closed": {"Opera": 3, "Brave": 0}}
    assert (await client.post("/api/v1/agent/browser-policy/report", headers=h, json=report)).status_code == 204
    state = (await client.get("/api/v1/guard/browser-policy/devices", headers=admin_headers)).json()[0]
    assert state["other_browsers"] == ["Brave", "Opera", "Tor Browser"]
    async with session_factory() as s:
        audit = (await s.execute(select(AuditLog).where(AuditLog.action == "guard.other_browser_closed"))).scalars().one()
    assert audit.detail == {"device": "OPERA-PC", "closed": {"Opera": 3}}

    # A report without closes adds nothing; an unknown name is refused.
    await client.post("/api/v1/agent/browser-policy/report", headers=h, json={"version": 1, "results": []})
    bogus = {"version": 1, "results": [], "closed": {"Call +1-555-0100": 1}}
    assert (await client.post("/api/v1/agent/browser-policy/report", headers=h, json=bogus)).status_code == 422
    async with session_factory() as s:
        assert len((await s.execute(select(AuditLog).where(AuditLog.action == "guard.other_browser_closed"))).all()) == 1


async def test_usb_modes_and_write_windows(client, admin_headers, user_headers, session_factory, admin_user):
    """C3: a USB mode on the policy, and in 'write on request' a window IT opens for one PC,
    served to that PC only, ended early or by time, audited."""
    await _guard_on(session_factory, admin_user.org_id)
    assert (await client.put("/api/v1/guard/browser-policy", headers=admin_headers,
                             json={**POLICY, "usb_mode": "everything"})).status_code == 422
    await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json={**POLICY, "usb_mode": "read_only"})
    did, h = await _enroll(client, admin_headers, "USB-PC")
    other, h2 = await _enroll(client, admin_headers, "OTHER-PC")
    assert (await client.get("/api/v1/agent/browser-policy", headers=h)).json()["policy"]["usb_mode"] == "read_only"

    # Not in 'write on request': there is no window to open.
    url = f"/api/v1/guard/devices/{did}/usb-window"
    assert (await client.post(url, headers=admin_headers, json={"minutes": 30})).status_code == 409

    await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json={**POLICY, "usb_mode": "on_request"})
    assert (await client.get("/api/v1/agent/usb-window", headers=h)).json() == {"until": None}
    for bad in ({"minutes": 5}, {"minutes": 481}, {"minutes": 30, "user": "x"}):
        assert (await client.post(url, headers=admin_headers, json=bad)).status_code == 422
    assert (await client.post(url, headers=user_headers, json={"minutes": 30})).status_code == 403
    opened = (await client.post(url, headers=admin_headers, json={"minutes": 30})).json()
    assert (await client.get("/api/v1/agent/usb-window", headers=h)).json()["until"] is not None
    assert (await client.get("/api/v1/agent/usb-window", headers=h2)).json() == {"until": None}   # that PC only

    await client.post("/api/v1/agent/browser-policy/report", headers=h, json={"version": 2, "results": [
        {"browser": "Usb", "removed": [r"{53f5630d-b6bf-11d0-94f2-00a0c91efb8b}\Deny_Write"]}]})
    row = next(d for d in (await client.get("/api/v1/guard/browser-policy/devices", headers=admin_headers)).json()
               if d["hostname"] == "USB-PC")
    assert row["usb_write_until"].rstrip("Z") == opened["until"].rstrip("Z") and row["results"][0]["browser"] == "Usb"
    assert row["usb_mode"] == "on_request"

    # Back to read-only for everyone: a window still on the books is not served.
    await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json={**POLICY, "usb_mode": "read_only"})
    assert (await client.get("/api/v1/agent/usb-window", headers=h)).json() == {"until": None}
    assert (await client.delete(url, headers=admin_headers)).status_code == 204
    assert (await client.delete(url, headers=admin_headers)).status_code == 404
    async with session_factory() as s:
        actions = [a.action for a in (await s.execute(select(AuditLog))).scalars()]
    assert "guard.usb_window_open" in actions and "guard.usb_window_close" in actions
    assert (await client.post(f"/api/v1/guard/devices/{other}/usb-window", headers=admin_headers,
                              json={"minutes": 30})).status_code == 409


async def test_usb_requests_from_the_tray(client, admin_headers, session_factory, admin_user):
    """C3b: the person asks from the tray; it waits on the Approvals page with its reason;
    approving it opens that PC's write window for the time chosen."""
    await _guard_on(session_factory, admin_user.org_id)
    await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json={**POLICY, "usb_mode": "read_only"})
    _, h = await _enroll(client, admin_headers, "MEENA-PC")
    ask = {"windows_user": r"ACME\meena", "reason": "presentation"}
    assert (await client.post("/api/v1/agent/usb-request", headers=h, json=ask)).status_code == 409   # not in that mode

    await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json={**POLICY, "usb_mode": "on_request"})
    for bad in ({**ask, "reason": "my boss said so"}, {**ask, "windows_user": "Call +1 555 now!"}, {**ask, "x": 1}):
        assert (await client.post("/api/v1/agent/usb-request", headers=h, json=bad)).status_code == 422, bad
    for _ in range(2):   # asked twice: one request
        assert (await client.post("/api/v1/agent/usb-request", headers=h, json=ask)).status_code == 202
    pending = [a for a in (await client.get("/api/v1/guard/approvals", headers=admin_headers)).json()
               if a["channel"] == "usb"]
    a = pending[0]
    assert len(pending) == 1 and (a["reason"], a["site"], a["status"]) == ("presentation", "usb", "pending")
    async with session_factory() as s:
        note = (await s.execute(select(Notification).where(Notification.title == "Approval requested"))).scalars().one()
    assert "USB" in note.message and "meena" not in note.message

    r = await client.post(f"/api/v1/guard/approvals/{a['id']}/approve", headers=admin_headers,
                          json={"minutes": 60, "requested_at": a["requested_at"]})
    assert r.status_code == 200, r.text
    assert (await client.get("/api/v1/agent/usb-window", headers=h)).json()["until"] is not None
    assert (await client.get("/api/v1/agent/guard/approvals", headers=h)).json() == []   # not a site approval


async def test_company_drives(client, admin_headers, user_headers, session_factory, admin_user):
    """C3b: PCs report the USB drives they have seen; an admin approves the company's own as part
    of the policy (a new version), and PCs in company_drives mode get only those."""
    await _guard_on(session_factory, admin_user.org_id)
    await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json=POLICY)
    _, h = await _enroll(client, admin_headers, "ACCOUNTS-PC")
    cruzer = r"USBSTOR\Disk&Ven_SanDisk&Prod_Cruzer&Rev_1.00\4C530001&0"
    generic = r"USBSTOR\Disk&Ven_General&Prod_USB_Disk&Rev_2.00\7&1a2b3c4d&0"
    report = {"version": 1, "results": [], "drives": [
        {"id": cruzer, "name": "SanDisk Cruzer USB Device", "unique_serial": True},
        {"id": generic, "name": "General USB Disk\u202e", "unique_serial": False}]}
    assert (await client.post("/api/v1/agent/browser-policy/report", headers=h, json=report)).status_code == 204
    bad = {**report, "drives": [{"id": r"SCSI\Disk&Ven_NVMe\5&1e9&0", "name": "x"}]}   # never an internal disk
    assert (await client.post("/api/v1/agent/browser-policy/report", headers=h, json=bad)).status_code == 422

    seen = (await client.get("/api/v1/guard/drives", headers=admin_headers)).json()
    assert {d["name"] for d in seen} == {"SanDisk Cruzer USB Device", "General USB Disk"}   # no invisible characters
    assert all(d["pcs"] == ["ACCOUNTS-PC"] and d["approved_in"] == [] for d in seen)
    assert (await client.get("/api/v1/guard/drives", headers=user_headers)).status_code == 403

    body = {**POLICY, "usb_mode": "company_drives",
            "usb_approved_drives": [{"id": cruzer, "name": " Accounts drive 1 "}, {"id": cruzer, "name": "dup"}]}
    r = (await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json=body)).json()
    assert r["version"] == 2 and r["policy"]["usb_approved_drives"] == [{"id": cruzer, "name": "Accounts drive 1"}]
    served = (await client.get("/api/v1/agent/browser-policy", headers=h)).json()["policy"]
    assert served["usb_mode"] == "company_drives" and served["usb_approved_drives"][0]["id"] == cruzer
    seen = {d["id"]: d for d in (await client.get("/api/v1/guard/drives", headers=admin_headers)).json()}
    assert seen[cruzer]["approved_in"] == ["Everyone"] and seen[generic]["unique_serial"] is False

    # 3b: drives by their USB interface (USB 3 UASP drives too), and the old disk form still accepted.
    uasp = r"USB\VID_04E8&PID_4001\S4UASP01"
    ok = (await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json={
        **body, "usb_approved_drives": [{"id": uasp, "name": "Samsung T7"}, {"id": cruzer, "name": "Cruzer"}]})).json()
    assert [d["id"] for d in ok["policy"]["usb_approved_drives"]] == [uasp, cruzer]
    for bad_drive in ({"id": "C:\\Windows", "name": "x"}, {"id": cruzer, "name": ""}, {"id": cruzer, "name": "a\u202eb"},
                      {"id": r"USB\VID_1234&PID_5678\5&2a3b4c&0&1", "name": "No serial"},
                      {"id": r"SCSI\Disk&Ven_NVMe\5&1e9&0", "name": "Internal"},
                      {"id": generic, "name": "No serial"}):   # review 3b L2: a made-up ID stands for no one drive
        bad_body = {**body, "usb_approved_drives": [bad_drive]}
        assert (await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json=bad_body)).status_code == 422


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


async def test_extensions_allowed_while_company_accounts_lock_the_browser(client, admin_headers, session_factory, admin_user):
    """Security review 3b M2: the admin lists the extensions that stay allowed when company accounts
    lock the browser; Chrome / Edge and Firefox IDs only, served to the PC as they are."""
    await _guard_on(session_factory, admin_user.org_id)
    _, h = await _enroll(client, admin_headers, "LOCK-PC")
    pm = "nngceckbapebfimnlniiiahkandclblb"
    body = {**POLICY, "claude_org_ids": ["aaaabbbb-0000-cccc-1111-dddd2222eeee"],
            "chrome_extension_id": "abcdefghijklmnopabcdefghijklmnop",
            "extension_allowlist": [pm, " {446900e4-71c2-419f-a6a7-df9c091e268b} ", pm, "1password@agilebits.com"]}
    r = await client.put("/api/v1/guard/browser-policy", headers=admin_headers, json=body)
    assert r.status_code == 200
    assert r.json()["policy"]["extension_allowlist"] == [pm, "{446900e4-71c2-419f-a6a7-df9c091e268b}", "1password@agilebits.com"]
    served = (await client.get("/api/v1/agent/browser-policy", headers=h)).json()["policy"]
    assert served["extension_allowlist"][0] == pm
    for bad in (["not an id"], ["javascript:alert(1)"], [pm] * 51):
        assert (await client.put("/api/v1/guard/browser-policy", headers=admin_headers,
                                 json={**body, "extension_allowlist": bad})).status_code == 422, bad


async def test_exceptions_layer_over_the_full_policy(client, admin_headers, session_factory, admin_user, regular_user):
    """An exception changes only its own modules of whatever full policy the person gets: USB
    allowed for one person of Sales keeps everything else of Sales. Every exception naming the
    person applies; where two set the same thing, the lower priority number wins."""
    await _guard_on(session_factory, admin_user.org_id)
    url = "/api/v1/guard/policies"
    served = lambda h: client.get("/api/v1/agent/browser-policy", headers=h)
    me = str(regular_user.id)
    await client.put("/api/v1/guard/browser-policy", headers=admin_headers,
                     json={**POLICY, "usb_mode": "block", "blocked_categories": ["social_media"]})
    team = (await client.post("/api/v1/grouping/teams", headers=admin_headers, json={"name": "Sales"})).json()["id"]
    await client.put(f"/api/v1/grouping/teams/{team}/users", headers=admin_headers, json={"user_ids": [me]})
    sales = (await client.post(url, headers=admin_headers, json={
        "name": "Sales", "priority": 5, "team_ids": [team],
        "policy": {**POLICY, "usb_mode": "read_only", "blocked_categories": ["social_media", "streaming"]}})).json()
    d, h = await _enroll(client, admin_headers, "SALES-2")
    assert (await client.post("/api/v1/assets", headers=admin_headers, json={
        "name": "Laptop", "device_id": d, "assigned_to_user_id": me})).status_code == 201
    base = (await served(h)).json()
    assert base["version"] == sales["version"] and base["policy"]["usb_mode"] == "read_only"

    # Bad exceptions are refused: empty, contradicting itself, company drives, or sent as a full policy.
    for bad in ({}, {"allow_sites": ["x.com"], "block_sites": ["x.com"]}, {"usb_mode": "company_drives"},
                {"allow_categories": ["shopping"], "block_categories": ["shopping"]}, {"made_up": True}):
        r = await client.post(url, headers=admin_headers, json={"name": "Bad", "priority": 1, "kind": "exception",
                                                                 "user_ids": [me], "exception": bad})
        assert r.status_code == 422, (bad, r.text)
    assert (await client.post(url, headers=admin_headers, json={"name": "Bad", "priority": 1, "kind": "exception",
                                                                "policy": POLICY})).status_code == 422

    usb = (await client.post(url, headers=admin_headers, json={
        "name": "USB allowed", "priority": 1, "kind": "exception", "user_ids": [me], "exception": {"usb_mode": "off"}})).json()
    assert usb["kind"] == "exception" and usb["policy"] is None and usb["exception"]["usb_mode"] == "off"
    p = (await served(h)).json()
    assert p["policy"]["usb_mode"] == "off"                                        # the exception's
    assert {"netflix.com", "facebook.com"} <= set(p["policy"]["blocked_sites"])  # Sales'
    assert p["version"] >= 1_000_000_000 and p["version"] != base["version"]

    # A second exception for the whole team: Facebook and personal Gmail allowed, USB read-only.
    # Its USB loses to the person's own exception (priority 1 beats 9); its sites still apply.
    fb = (await client.post(url, headers=admin_headers, json={
        "name": "Facebook and Gmail", "priority": 9, "kind": "exception", "team_ids": [team],
        "exception": {"allow_sites": ["facebook.com"], "google_allowed_domains": [], "usb_mode": "read_only"}})).json()
    p2 = (await served(h)).json()
    assert p2["policy"]["usb_mode"] == "off" and p2["policy"]["google_allowed_domains"] == []
    assert {"facebook.com"} <= set(p2["policy"]["allowed_sites"]) and {"facebook.com"}.isdisjoint(p2["policy"]["blocked_sites"])
    assert p2["version"] != p["version"] and (await served(h)).json()["version"] == p2["version"]   # stable

    # An exception keeps its kind, and the PC list names the exceptions on each PC.
    assert (await client.put(f"{url}/{fb['id']}", headers=admin_headers, json={
        "name": "Facebook and Gmail", "priority": 9, "team_ids": [team], "policy": POLICY})).status_code == 409
    await client.post("/api/v1/agent/browser-policy/report", headers=h, json={"version": p2["version"], "results": []})
    row = next(x for x in (await client.get("/api/v1/guard/browser-policy/devices", headers=admin_headers)).json()
               if x["hostname"] == "SALES-2")
    assert row["policy_name"] == "Sales" and row["exceptions"] == ["USB allowed", "Facebook and Gmail"]
    assert row["policy_version"] == p2["version"] and row["usb_mode"] == "off"

    # Without the full policy, the exceptions sit on the default one.
    await client.delete(f"{url}/{sales['id']}", headers=admin_headers)
    p3 = (await served(h)).json()["policy"]
    assert p3["usb_mode"] == "off" and {"netflix.com"}.isdisjoint(p3["blocked_sites"])
    assert {"facebook.com"} <= set(p3["allowed_sites"])


async def test_categories_can_be_allowed(client, admin_headers, session_factory, admin_user, regular_user):
    """A category can be allowed as well as blocked, in a full policy or an exception."""
    await _guard_on(session_factory, admin_user.org_id)
    put = lambda body: client.put("/api/v1/guard/browser-policy", headers=admin_headers, json=body)
    assert (await put({"blocked_categories": ["work_tools"], "allowed_categories": ["work_tools"]})).status_code == 422
    r = await put({"blocked_sites": ["zoom.us"], "blocked_categories": ["streaming"], "allowed_categories": ["work_tools"]})
    assert r.status_code == 200 and r.json()["policy"]["allowed_categories"] == ["work_tools"]
    d, h = await _enroll(client, admin_headers, "CAT-1")
    p = (await client.get("/api/v1/agent/browser-policy", headers=h)).json()["policy"]
    assert {"office.com", "zoom.us"} <= set(p["allowed_sites"])          # allowed wins on the PC
    assert {"youtube.com"} <= set(p["blocked_sites"]) and "allowed_categories" not in p

    me = str(regular_user.id)
    await client.post("/api/v1/assets", headers=admin_headers, json={"name": "L", "device_id": d, "assigned_to_user_id": me})
    await client.post("/api/v1/guard/policies", headers=admin_headers, json={
        "name": "No video calls, but YouTube", "priority": 1, "kind": "exception", "user_ids": [me],
        "exception": {"block_categories": ["work_tools"], "allow_categories": ["streaming"]}})
    p = (await client.get("/api/v1/agent/browser-policy", headers=h)).json()["policy"]
    assert {"office.com"} <= set(p["blocked_sites"]) and {"office.com"}.isdisjoint(p["allowed_sites"])
    assert {"youtube.com"} <= set(p["allowed_sites"]) and {"youtube.com"}.isdisjoint(p["blocked_sites"])
    cats = {c["key"] for c in (await client.get("/api/v1/guard/site-categories", headers=admin_headers)).json()}
    assert {"streaming", "gaming", "gambling", "shopping", "job_search", "dating", "vpn_proxy", "piracy", "work_tools"} <= cats
