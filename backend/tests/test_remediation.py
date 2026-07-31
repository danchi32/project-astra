"""Self-healing / remediation tests. Security-critical: the tier system must be
enforced server-side so a lower-tier action can never execute without approval and
a lower role can never approve a higher-tier action."""


from tests.conftest import USER_PASSWORD, _create_user, auth_headers
from app.models import UserRole


async def _enroll(client, admin_headers, hostname="RMD-PC", machine="rmd-machine"):
    tok = await client.post(
        "/api/v1/devices/enrollment-tokens", json={"name": "rmd"}, headers=admin_headers
    )
    enroll = await client.post(
        "/api/v1/agent/enroll",
        json={
            "enrollment_token": tok.json()["token"],
            "hostname": hostname,
            "machine_id": machine,
            "os_version": "Windows 11",
            "agent_version": "0.1.0",
        },
    )
    return enroll.json()  # device_id, device_token


async def _device_id(client, admin_headers):
    devices = await client.get("/api/v1/devices", headers=admin_headers)
    return devices.json()[0]["id"]


# ── Tier enforcement (the security core) ──────────────────────────────────


async def test_automatic_action_is_auto_approved(client, admin_headers):
    await _enroll(client, admin_headers)
    device_id = await _device_id(client, admin_headers)
    resp = await client.post(
        "/api/v1/remediations",
        json={"device_id": device_id, "action_id": "flush_dns", "reason": "site won't load"},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "approved"  # no human approval needed
    assert resp.json()["tier"] == "automatic"


async def test_approval_required_action_starts_pending(client, admin_headers):
    await _enroll(client, admin_headers)
    device_id = await _device_id(client, admin_headers)
    resp = await client.post(
        "/api/v1/remediations",
        json={"device_id": device_id, "action_id": "office_repair", "reason": "office broken"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending_approval"
    assert resp.json()["tier"] == "approval_required"


async def test_create_outlook_rule_is_an_automatic_action_with_params(client, admin_headers):
    """The AI-driven 'create a rule from X, move to folder Y' path: a real action
    (auto-applied), with the sender + folder carried as params to the agent."""
    await _enroll(client, admin_headers)
    device_id = await _device_id(client, admin_headers)
    resp = await client.post(
        "/api/v1/remediations", headers=admin_headers,
        json={
            "device_id": device_id, "action_id": "create_outlook_rule",
            "reason": "User asked to file this sender into a folder",
            "params": {"from_address": "chishtydanish@gmail.com", "folder_name": "Danish"},
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["action_id"] == "create_outlook_rule"
    assert body["tier"] == "automatic"
    assert body["status"] == "approved"  # action, not a queued suggestion

    # The sender + folder are stored on the task, so the agent receives them to build the rule.
    tasks = (await client.get("/api/v1/remediations", headers=admin_headers)).json()["items"]
    rule_task = next(t for t in tasks if t["action_id"] == "create_outlook_rule")
    assert rule_task["params"] == {"from_address": "chishtydanish@gmail.com", "folder_name": "Danish"}


async def test_create_outlook_rule_rejects_bad_email(client, admin_headers):
    await _enroll(client, admin_headers)
    device_id = await _device_id(client, admin_headers)
    r = await client.post("/api/v1/remediations", headers=admin_headers, json={
        "device_id": device_id, "action_id": "create_outlook_rule", "reason": "x",
        "params": {"from_address": "not-an-email", "folder_name": "Danish"}})
    assert r.status_code == 400
    assert "email" in r.text.lower()


async def test_create_outlook_rule_rejects_unsafe_folder(client, admin_headers):
    await _enroll(client, admin_headers)
    device_id = await _device_id(client, admin_headers)
    r = await client.post("/api/v1/remediations", headers=admin_headers, json={
        "device_id": device_id, "action_id": "create_outlook_rule", "reason": "x",
        "params": {"from_address": "a@b.com", "folder_name": "bad/../path"}})
    assert r.status_code == 400
    assert "folder" in r.text.lower()


async def test_admin_only_action_cannot_run_via_automatic_path(client, admin_headers):
    """SECURITY INVARIANT — must fail loudly if ever broken: an admin_only action can
    NEVER dispatch to an agent without explicit admin approval, even though the org's
    automatic-approval switch is ON (it's on by default — see the automatic test)."""
    enroll = await _enroll(client, admin_headers)
    device_id = await _device_id(client, admin_headers)
    device_headers = {"Authorization": f"Bearer {enroll['device_token']}"}

    resp = await client.post(
        "/api/v1/remediations", headers=admin_headers,
        json={"device_id": device_id, "action_id": "reset_windows_update_components", "reason": "x"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["tier"] == "admin_only"
    assert resp.json()["status"] == "pending_approval", \
        "CRITICAL: an admin_only action was auto-approved through the automatic path"

    # The agent must not be able to claim it — only APPROVED tasks ever dispatch.
    claim = await client.get("/api/v1/agent/tasks", headers=device_headers)
    dispatched = [t["action_id"] for t in claim.json()]
    assert "reset_windows_update_components" not in dispatched, \
        "CRITICAL: an admin_only action reached an agent without approval"


async def test_fleet_circuit_breaker_and_hard_cap(client, admin_headers, monkeypatch):
    """Blast-radius limit: past a burst threshold, even automatic actions require a
    human; past the hard threshold, new remediations are refused outright."""
    import app.services.remediation.service as rem
    monkeypatch.setattr(rem.settings, "remediation_auto_approve_burst", 2)
    monkeypatch.setattr(rem.settings, "remediation_hard_burst", 4)

    # One fix pushed across many machines — the breaker counts per ORG, so this is the
    # blast radius it exists to limit. It used to be tested by firing the same action at
    # one device five times, which duplicate suppression now (correctly) refuses; that was
    # never what a runaway push looks like anyway.
    devices = []
    for i in range(5):
        await _enroll(client, admin_headers, hostname=f"RMD-{i}", machine=f"rmd-machine-{i}")
        devices.append((await client.get("/api/v1/devices", headers=admin_headers)).json())
    device_ids = [d["id"] for d in devices[-1]]

    async def make(device_id):
        return await client.post(
            "/api/v1/remediations", headers=admin_headers,
            json={"device_id": device_id, "action_id": "flush_dns", "reason": "x"},
        )

    statuses = []
    for device_id in device_ids[:4]:
        r = await make(device_id)
        assert r.status_code == 201, r.text
        statuses.append(r.json()["status"])
    # First two auto-approve; the breaker then forces human approval.
    assert statuses == ["approved", "approved", "pending_approval", "pending_approval"]

    # Beyond the hard burst, new remediations are refused.
    blocked = await make(device_ids[4])
    assert blocked.status_code == 400
    assert "safety limit" in blocked.text.lower()


async def test_technician_can_approve_approval_required_but_not_admin_only(
    client, admin_headers, session_factory, org
):
    await _enroll(client, admin_headers)
    device_id = await _device_id(client, admin_headers)
    tech = await _create_user(
        session_factory, org.id, "tech@acme.com", USER_PASSWORD, UserRole.TECHNICIAN
    )
    tech_headers = await auth_headers(client, tech.email, USER_PASSWORD)

    # approval_required → technician CAN approve
    ar = await client.post(
        "/api/v1/remediations",
        json={"device_id": device_id, "action_id": "network_reset", "reason": "no internet"},
        headers=admin_headers,
    )
    approve = await client.post(
        f"/api/v1/remediations/{ar.json()['id']}/approve", headers=tech_headers
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"

    # admin_only → technician CANNOT approve
    ao = await client.post(
        "/api/v1/remediations",
        json={"device_id": device_id, "action_id": "registry_fix", "params": {"fix_id": "x"},
              "reason": "registry"},
        headers=admin_headers,
    )
    denied = await client.post(
        f"/api/v1/remediations/{ao.json()['id']}/approve", headers=tech_headers
    )
    assert denied.status_code == 403  # technician cannot clear an admin-only action

    # admin_only → admin CAN approve
    ok = await client.post(
        f"/api/v1/remediations/{ao.json()['id']}/approve", headers=admin_headers
    )
    assert ok.status_code == 200


async def test_regular_user_cannot_create_or_approve(client, admin_headers, user_headers):
    await _enroll(client, admin_headers)
    device_id = await _device_id(client, admin_headers)
    # Create as admin so there's a pending task
    ar = await client.post(
        "/api/v1/remediations",
        json={"device_id": device_id, "action_id": "office_repair", "reason": "x"},
        headers=admin_headers,
    )
    # Regular user can neither create nor approve
    create = await client.post(
        "/api/v1/remediations",
        json={"device_id": device_id, "action_id": "flush_dns", "reason": "x"},
        headers=user_headers,
    )
    assert create.status_code == 403
    approve = await client.post(
        f"/api/v1/remediations/{ar.json()['id']}/approve", headers=user_headers
    )
    assert approve.status_code == 403


async def test_unknown_action_and_bad_service_rejected(client, admin_headers):
    await _enroll(client, admin_headers)
    device_id = await _device_id(client, admin_headers)
    bad_action = await client.post(
        "/api/v1/remediations",
        json={"device_id": device_id, "action_id": "delete_everything", "reason": "x"},
        headers=admin_headers,
    )
    assert bad_action.status_code == 400
    bad_service = await client.post(
        "/api/v1/remediations",
        json={"device_id": device_id, "action_id": "restart_service",
              "params": {"service_name": "LSASS"}, "reason": "x"},
        headers=admin_headers,
    )
    assert bad_service.status_code == 400  # not on the allowlist


# ── Agent execution flow ──────────────────────────────────────────────────


async def test_agent_claims_and_reports_result(client, admin_headers):
    enroll = await _enroll(client, admin_headers)
    device_headers = {"Authorization": f"Bearer {enroll['device_token']}"}
    device_id = await _device_id(client, admin_headers)

    await client.post(
        "/api/v1/remediations",
        json={"device_id": device_id, "action_id": "restart_outlook", "reason": "hung"},
        headers=admin_headers,
    )
    # Agent claims approved tasks
    claim = await client.get("/api/v1/agent/tasks", headers=device_headers)
    assert claim.status_code == 200
    assert len(claim.json()) == 1
    task = claim.json()[0]
    assert task["action_id"] == "restart_outlook"

    # Claiming again returns nothing (already dispatched)
    again = await client.get("/api/v1/agent/tasks", headers=device_headers)
    assert again.json() == []

    # Agent reports success
    result = await client.post(
        f"/api/v1/agent/tasks/{task['id']}/result",
        json={"success": True, "output": "Outlook restarted."},
        headers=device_headers,
    )
    assert result.status_code == 204

    # Portal sees it succeeded
    tasks = await client.get("/api/v1/remediations", headers=admin_headers)
    row = next(t for t in tasks.json()["items"] if t["id"] == task["id"])
    assert row["status"] == "succeeded"
    assert row["result"]["output"] == "Outlook restarted."


async def test_agent_only_claims_own_devices_tasks(client, admin_headers):
    a = await _enroll(client, admin_headers, "DEV-A", "mach-a")
    b = await _enroll(client, admin_headers, "DEV-B", "mach-b")
    # Task for device A
    await client.post(
        "/api/v1/remediations",
        json={"device_id": a["device_id"], "action_id": "flush_dns", "reason": "x"},
        headers=admin_headers,
    )
    # Device B claims — should get nothing
    b_headers = {"Authorization": f"Bearer {b['device_token']}"}
    claim = await client.get("/api/v1/agent/tasks", headers=b_headers)
    assert claim.json() == []


async def test_tasks_endpoint_requires_device_token(client, admin_headers):
    resp = await client.get("/api/v1/agent/tasks", headers=admin_headers)
    assert resp.status_code == 401


# ── AI-driven remediation (via the device chat) ────────────────────────────


async def test_ai_applies_automatic_fix_from_device_chat(client, admin_headers):
    enroll = await _enroll(client, admin_headers)
    device_headers = {"Authorization": f"Bearer {enroll['device_token']}"}

    # The stub proposes restart_outlook when a user reports Outlook crashing.
    chat = await client.post(
        "/api/v1/agent/chat",
        json={"content": "outlook keeps crashing, can you fix it?"},
        headers=device_headers,
    )
    assert chat.status_code == 200
    trail = chat.json()["tool_trail"]
    assert any(step["tool"] == "propose_remediation" for step in trail)

    # A task was created and auto-approved, waiting for the agent.
    claim = await client.get("/api/v1/agent/tasks", headers=device_headers)
    assert len(claim.json()) == 1
    assert claim.json()[0]["action_id"] == "restart_outlook"


async def test_actions_catalogue_lists_tiers(client, user_headers):
    resp = await client.get("/api/v1/remediations/actions", headers=user_headers)
    assert resp.status_code == 200
    by_id = {a["id"]: a for a in resp.json()}
    assert by_id["flush_dns"]["tier"] == "automatic"
    assert by_id["office_repair"]["tier"] == "approval_required"
    assert by_id["registry_fix"]["tier"] == "admin_only"


async def test_inline_approval_skips_the_pending_state_and_its_notification(
    client, admin_headers, session_factory
):
    """The reported bug: pushing a fix from the portal always raised an "Approval needed"
    notification for something approved milliseconds later, and the approval queue was
    therefore always empty by the time anyone looked."""
    await _enroll(client, admin_headers)
    device_id = await _device_id(client, admin_headers)

    r = await client.post("/api/v1/remediations", headers=admin_headers, json={
        "device_id": device_id, "action_id": "office_repair",   # approval_required tier
        "reason": "portal push", "approve": True,
    })
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "approved"          # never sat pending

    notes = (await client.get("/api/v1/notifications", headers=admin_headers)).json()["items"]
    assert not any("Approval needed" in (n.get("title") or "") for n in notes), notes


async def test_without_approve_the_task_waits_and_notifies(client, admin_headers, session_factory):
    """The queue must still work for everything that genuinely needs a human."""
    await _enroll(client, admin_headers)
    device_id = await _device_id(client, admin_headers)

    r = await client.post("/api/v1/remediations", headers=admin_headers, json={
        "device_id": device_id, "action_id": "office_repair", "reason": "needs a human",
    })
    assert r.json()["status"] == "pending_approval"

    notes = (await client.get("/api/v1/notifications", headers=admin_headers)).json()["items"]
    assert any("Approval needed" in (n.get("title") or "") for n in notes)


async def test_inline_approval_still_enforces_the_tier(client, user_headers, admin_headers):
    """approve=true is not a way around the trust tiers — a plain user may approve nothing,
    and the refusal must leave no half-created task behind."""
    await _enroll(client, admin_headers)
    device_id = await _device_id(client, admin_headers)

    r = await client.post("/api/v1/remediations", headers=user_headers, json={
        "device_id": device_id, "action_id": "office_repair",
        "reason": "should be refused", "approve": True,
    })
    assert r.status_code in (400, 403), r.text

    tasks = (await client.get("/api/v1/remediations", headers=admin_headers)).json()["items"]
    assert not any(t["action_id"] == "office_repair" for t in tasks), "a refused push must create nothing"


# ── Duplicate suppression ─────────────────────────────────────────────────


async def test_same_action_cannot_be_queued_twice_on_one_device(client, admin_headers):
    """A long action shows no progress while it runs, so an operator who sees nothing
    happen presses the button again. Three identical Windows Update installs were queued
    on one machine that way; the agent runs them one after another, so the device stays
    tied up for three times as long doing work it was asked to do once."""
    await _enroll(client, admin_headers)
    device_id = await _device_id(client, admin_headers)
    body = {"device_id": device_id, "action_id": "flush_dns", "reason": "site won't load"}

    first = await client.post("/api/v1/remediations", json=body, headers=admin_headers)
    assert first.status_code == 201

    second = await client.post("/api/v1/remediations", json=body, headers=admin_headers)
    # 409, not 400: the request was fine and the work is already under way.
    assert second.status_code == 409, second.text
    assert "already" in second.json()["detail"].lower()

    tasks = await client.get("/api/v1/remediations", headers=admin_headers)
    assert len([t for t in tasks.json()["items"] if t["action_id"] == "flush_dns"]) == 1


async def test_a_different_parameter_is_different_work(client, admin_headers):
    """Pushing two specific updates is two jobs, not a duplicate. The guard keys on
    params as well as the action, or 'fix all' per KB would only ever push the first KB."""
    await _enroll(client, admin_headers)
    device_id = await _device_id(client, admin_headers)

    a = await client.post(
        "/api/v1/remediations",
        json={"device_id": device_id, "action_id": "restart_service",
              "params": {"service_name": "Spooler"}, "reason": "printing stuck"},
        headers=admin_headers,
    )
    b = await client.post(
        "/api/v1/remediations",
        json={"device_id": device_id, "action_id": "restart_service",
              "params": {"service_name": "WSearch"}, "reason": "search broken"},
        headers=admin_headers,
    )
    assert a.status_code == 201, a.text
    assert b.status_code == 201, b.text


async def test_the_same_action_is_allowed_again_once_it_has_finished(client, admin_headers):
    """The guard covers work in flight only. A fix that already ran must be repeatable —
    flushing DNS twice in a day is normal, and refusing it would be worse than the bug."""
    enroll = await _enroll(client, admin_headers)
    device_headers = {"Authorization": f"Bearer {enroll['device_token']}"}
    device_id = await _device_id(client, admin_headers)
    body = {"device_id": device_id, "action_id": "flush_dns", "reason": "site won't load"}

    first = await client.post("/api/v1/remediations", json=body, headers=admin_headers)
    task_id = first.json()["id"]

    await client.get("/api/v1/agent/tasks", headers=device_headers)
    done = await client.post(
        f"/api/v1/agent/tasks/{task_id}/result",
        json={"success": True, "output": "flushed"},
        headers=device_headers,
    )
    assert done.status_code == 204

    again = await client.post("/api/v1/remediations", json=body, headers=admin_headers)
    assert again.status_code == 201, again.text


async def test_bulk_push_reports_already_running_apart_from_failures(client, admin_headers):
    """'Fix all' must not call an already-running device a failure — that reads as
    'the push didn't work' and invites a second press, which is what creates duplicates."""
    await _enroll(client, admin_headers)
    device_id = await _device_id(client, admin_headers)
    await client.post(
        "/api/v1/remediations",
        json={"device_id": device_id, "action_id": "clear_system_temp", "reason": "low disk"},
        headers=admin_headers,
    )

    bulk = await client.post(
        "/api/v1/fleet/remediate",
        json={"device_ids": [device_id], "action_id": "clear_system_temp", "reason": "low disk"},
        headers=admin_headers,
    )
    assert bulk.status_code == 200, bulk.text
    body = bulk.json()
    assert body["already_running"] == 1
    assert body["queued"] == 0
    assert body["failed"] == 0
