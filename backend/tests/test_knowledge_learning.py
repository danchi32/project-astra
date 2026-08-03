"""The knowledge base learning from fixes that actually worked.

The value of this feature is entirely in its restraint. A base that grows by one article per
chat is worse than one that never grows at all — hand-written runbooks stop being findable,
and the assistant starts answering from a pile of near-duplicates. So most of what is pinned
here is what learning must NOT do.
"""
import pytest

from app.models import KnowledgeArticle, KnowledgeSource
from app.services.ai import learning
from app.services.ai.knowledge import KnowledgeBaseService


async def _confirm(session_factory, org_id, *, symptom, success=True,
                   action_id="restart_outlook", label="Restart Outlook", params=None):
    async with session_factory() as session:
        article = await KnowledgeBaseService(session).learn_from_fix(
            org_id=org_id, action_id=action_id, action_label=label,
            params=params, symptom=symptom, success=success,
        )
        await session.commit()
        return article


async def _learned(session_factory, org_id, action_id="restart_outlook"):
    from app.repositories.knowledge import KnowledgeRepository

    async with session_factory() as session:
        return await KnowledgeRepository(session).get_learned(
            org_id=org_id, action_id=action_id
        )


async def _search(session_factory, org_id, query):
    async with session_factory() as session:
        return await KnowledgeBaseService(session).search(org_id=org_id, query=query)


# ── The restraint ──────────────────────────────────────────────────────────


async def test_one_success_does_not_become_searchable(session_factory, admin_user):
    """A single fix is an anecdote. It is recorded, but the assistant must not start
    quoting it as documented practice."""
    await _confirm(session_factory, admin_user.org_id, symptom="outlook is not responding")

    article = await _learned(session_factory, admin_user.org_id)
    assert article is not None, "the attempt should still be recorded"
    assert article.published_at is None
    assert article.source is KnowledgeSource.RESOLVED_ISSUE

    assert await _search(session_factory, admin_user.org_id, "outlook not responding") == []


async def test_three_successes_publish_it(session_factory, admin_user):
    for phrasing in ("outlook is not responding", "outlook keeps freezing",
                     "my outlook hangs on startup"):
        await _confirm(session_factory, admin_user.org_id, symptom=phrasing)

    article = await _learned(session_factory, admin_user.org_id)
    assert article.published_at is not None
    assert article.successes == 3

    hits = await _search(session_factory, admin_user.org_id, "outlook is not responding")
    assert [a.id for a in hits] == [article.id]


async def test_repeats_update_one_article_rather_than_piling_up(session_factory, admin_user):
    """The failure mode this whole design exists to prevent: forty chats about Outlook
    producing forty articles about Outlook."""
    for i in range(8):
        await _confirm(session_factory, admin_user.org_id, symptom=f"outlook problem number {i}")

    async with session_factory() as session:
        rows, total = await KnowledgeBaseService(session).list_page(org_id=admin_user.org_id)
    assert total == 1, [r.title for r in rows]


async def test_different_fixes_stay_separate(session_factory, admin_user):
    await _confirm(session_factory, admin_user.org_id, symptom="outlook stuck")
    await _confirm(session_factory, admin_user.org_id, symptom="no internet",
                   action_id="flush_dns", label="Flush DNS cache")

    async with session_factory() as session:
        _, total = await KnowledgeBaseService(session).list_page(org_id=admin_user.org_id)
    assert total == 2


async def test_the_same_action_on_different_targets_stays_separate(session_factory, admin_user):
    """"Restart an application" is not one runbook — restarting Chrome and restarting
    Notepad share an action id and nothing else."""
    await _confirm(session_factory, admin_user.org_id, symptom="chrome won't open",
                   action_id="restart_application", label="Restart an application",
                   params={"process_name": "chrome"})
    await _confirm(session_factory, admin_user.org_id, symptom="teams won't load",
                   action_id="restart_application", label="Restart an application",
                   params={"process_name": "ms-teams"})

    async with session_factory() as session:
        _, total = await KnowledgeBaseService(session).list_page(org_id=admin_user.org_id)
    assert total == 2


async def test_a_first_time_failure_teaches_nothing(session_factory, admin_user):
    """There is no fix here to document — only an attempt that didn't work."""
    await _confirm(session_factory, admin_user.org_id, symptom="printer is offline",
                   success=False, action_id="restart_spooler", label="Restart Print Spooler")
    assert await _learned(session_factory, admin_user.org_id, "restart_spooler") is None


async def test_an_unexplained_fix_teaches_nothing(session_factory, admin_user):
    """No symptom, no runbook. An article titled after the action alone tells a future
    reader nothing they couldn't get from the action list."""
    await _confirm(session_factory, admin_user.org_id, symptom="")
    assert await _learned(session_factory, admin_user.org_id) is None


# ── Staying honest after publication ───────────────────────────────────────


async def test_a_fix_that_stops_working_stops_being_recommended(session_factory, admin_user):
    """The article this protects against is the dangerous one: eleven successes, published,
    and then the fix quietly stops working after a Windows update. Without this it keeps
    being handed to the assistant as settled truth.
    """
    for i in range(3):
        await _confirm(session_factory, admin_user.org_id, symptom=f"outlook frozen {i}")
    assert await _search(session_factory, admin_user.org_id, "outlook frozen") != []

    for i in range(5):
        await _confirm(session_factory, admin_user.org_id, symptom=f"outlook frozen again {i}",
                       success=False)

    article = await _learned(session_factory, admin_user.org_id)
    assert article.successes == 3 and article.failures == 5
    # Still on record for staff to read — just no longer offered as an answer.
    assert article.published_at is not None
    assert await _search(session_factory, admin_user.org_id, "outlook frozen") == []


async def test_a_failure_does_not_donate_its_wording(session_factory, admin_user):
    """A phrasing this fix did NOT resolve is precisely the wording that should not pull
    this article up for the next person."""
    for i in range(3):
        await _confirm(session_factory, admin_user.org_id, symptom=f"outlook hangs {i}")
    await _confirm(session_factory, admin_user.org_id,
                   symptom="calendar invites vanish", success=False)

    article = await _learned(session_factory, admin_user.org_id)
    assert not any("calendar" in s for s in article.symptom_samples)


async def test_evidence_is_stated_in_the_article(session_factory, admin_user):
    for i in range(3):
        await _confirm(session_factory, admin_user.org_id, symptom=f"outlook wedged {i}")
    await _confirm(session_factory, admin_user.org_id, symptom="outlook wedged x", success=False)

    article = await _learned(session_factory, admin_user.org_id)
    assert "3 succeeded" in article.content and "1 failed" in article.content


async def test_samples_are_capped(session_factory, admin_user):
    for i in range(20):
        await _confirm(session_factory, admin_user.org_id, symptom=f"distinct outlook symptom {i}")
    article = await _learned(session_factory, admin_user.org_id)
    assert len(article.symptom_samples) == learning.MAX_SAMPLES


async def test_identical_wording_is_not_stored_twice(session_factory, admin_user):
    for _ in range(4):
        await _confirm(session_factory, admin_user.org_id, symptom="Outlook Is Not Responding")
    article = await _learned(session_factory, admin_user.org_id)
    assert len(article.symptom_samples) == 1
    assert article.successes == 4


# ── What must not leak ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,gone",
    [
        ("cant mail priya.sharma@lancesoft.com anymore", "priya.sharma@lancesoft.com"),
        ("cant reach \\\\FS01\\payroll\\salaries", "FS01"),
        ("account 4539 8871 2234 9910 is locked", "4539 8871 2234 9910"),
    ],
)
def test_identifiers_are_stripped_before_they_become_an_article(raw, gone):
    """This text stops being a private message and becomes a document everyone in the
    organization can read."""
    assert gone not in learning.redact(raw)


async def test_learning_is_org_scoped(session_factory, admin_user, other_org):
    for i in range(3):
        await _confirm(session_factory, admin_user.org_id, symptom=f"outlook broken {i}")
    assert await _search(session_factory, other_org.id, "outlook broken") == []
    assert await _learned(session_factory, other_org.id) is None


async def test_learning_never_rewrites_a_hand_written_runbook(session_factory, admin_user):
    """A technician's article is authored, reviewed and owned. The learning path must be
    incapable of editing it, even when it covers the same action."""
    async with session_factory() as session:
        svc = KnowledgeBaseService(session)
        manual = await svc.create(
            org_id=admin_user.org_id, title="Outlook: the approved procedure",
            content="Follow the Exchange team's documented steps.",
        )
        manual_id, original = manual.id, manual.content

    for i in range(4):
        await _confirm(session_factory, admin_user.org_id, symptom=f"outlook down {i}")

    async with session_factory() as session:
        after = await session.get(KnowledgeArticle, manual_id)
    assert after.content == original
    assert after.source is KnowledgeSource.MANUAL


# ── Manual articles keep working exactly as before ─────────────────────────


async def test_a_hand_written_article_is_searchable_immediately(session_factory, admin_user):
    """No thresholds for a human. Someone typed it because they wanted it used."""
    async with session_factory() as session:
        svc = KnowledgeBaseService(session)
        await svc.create(org_id=admin_user.org_id, title="Connecting to the VPN",
                         content="Open GlobalConnect and authenticate with MFA.")
        hits = await svc.search(org_id=admin_user.org_id, query="connecting to the VPN")
    assert [a.title for a in hits] == ["Connecting to the VPN"]


async def test_a_global_article_is_searchable_immediately(session_factory, admin_user):
    async with session_factory() as session:
        svc = KnowledgeBaseService(session)
        await svc.create_global(title="Windows update stuck at 0%",
                                content="Clear SoftwareDistribution and retry.")
        hits = await svc.search(org_id=admin_user.org_id, query="windows update stuck")
    assert [a.title for a in hits] == ["Windows update stuck at 0%"]


# ── End to end, through the agent's own result path ────────────────────────


async def test_a_chat_fix_teaches_the_base_end_to_end(client, admin_headers, session_factory):
    """The whole point, exercised the way it will actually happen: a user complains in the
    tray chat, the assistant fixes it, the agent reports the result — three times."""
    tok = await client.post(
        "/api/v1/devices/enrollment-tokens", json={"name": "learn"}, headers=admin_headers
    )
    enrolled = (await client.post("/api/v1/agent/enroll", json={
        "enrollment_token": tok.json()["token"], "hostname": "LEARN-PC",
        "machine_id": "learn-pc", "os_version": "Windows 11", "agent_version": "0.7.4",
    })).json()
    device_headers = {"Authorization": f"Bearer {enrolled['device_token']}"}

    org_id = None
    for _ in range(3):
        chat = await client.post(
            "/api/v1/agent/chat",
            json={"content": "outlook is not responding again"},
            headers=device_headers,
        )
        assert chat.status_code == 200, chat.text

        claimed = (await client.get("/api/v1/agent/tasks", headers=device_headers)).json()
        if not claimed:
            pytest.skip("the stub assistant proposed no remediation for this phrasing")
        for task in claimed:
            await client.post(
                f"/api/v1/agent/tasks/{task['id']}/result",
                json={"success": True, "output": "Outlook restarted"},
                headers=device_headers,
            )

    from sqlalchemy import select

    from app.models import Device

    async with session_factory() as session:
        org_id = (await session.execute(
            select(Device.org_id).where(Device.machine_id == "learn-pc")
        )).scalar_one()

    async with session_factory() as session:
        rows, _ = await KnowledgeBaseService(session).list_page(org_id=org_id)
    learned = [r for r in rows if r.source is KnowledgeSource.RESOLVED_ISSUE]
    assert learned, "three confirmed chat fixes should have taught the base something"
    assert learned[0].published_at is not None
    assert "outlook is not responding again" in learned[0].content


async def test_a_result_still_records_when_learning_cannot(
    client, admin_headers, session_factory, monkeypatch
):
    """Learning is bookkeeping on the agent's result path. If it throws, the outcome of a
    fix that has already run on a real machine must still be written down."""
    async def boom(*args, **kwargs):
        raise RuntimeError("embedding backend is down")

    monkeypatch.setattr(KnowledgeBaseService, "learn_from_fix", boom)

    tok = await client.post(
        "/api/v1/devices/enrollment-tokens", json={"name": "resil"}, headers=admin_headers
    )
    enrolled = (await client.post("/api/v1/agent/enroll", json={
        "enrollment_token": tok.json()["token"], "hostname": "RESIL-PC",
        "machine_id": "resil-pc", "os_version": "Windows 11", "agent_version": "0.7.4",
    })).json()
    device_headers = {"Authorization": f"Bearer {enrolled['device_token']}"}

    await client.post("/api/v1/agent/chat",
                      json={"content": "outlook is not responding"}, headers=device_headers)
    claimed = (await client.get("/api/v1/agent/tasks", headers=device_headers)).json()
    if not claimed:
        pytest.skip("the stub assistant proposed no remediation for this phrasing")

    resp = await client.post(
        f"/api/v1/agent/tasks/{claimed[0]['id']}/result",
        json={"success": True, "output": "done"},
        headers=device_headers,
    )
    assert resp.status_code == 204, resp.text

    # And the outcome is genuinely on record, not merely un-rejected.
    from sqlalchemy import select

    from app.models import RemediationStatus, RemediationTask

    async with session_factory() as session:
        status = (await session.execute(
            select(RemediationTask.status).where(RemediationTask.id == claimed[0]["id"])
        )).scalar_one()
    assert status is RemediationStatus.SUCCEEDED


async def test_staff_can_see_what_the_platform_is_teaching_itself(
    client, admin_headers, admin_user, session_factory
):
    """Learned articles are visible from the first confirmation, clearly marked as not yet
    in use. Learning that happens invisibly is learning nobody can correct."""
    await _confirm(session_factory, admin_user.org_id, symptom="outlook wont open")

    body = (await client.get("/api/v1/knowledge", headers=admin_headers)).json()
    row = next(a for a in body["items"] if a["source"] == "resolved_issue")
    assert row["learning_status"] == "learning"
    assert row["published_at"] is None

    for i in range(2):
        await _confirm(session_factory, admin_user.org_id, symptom=f"outlook dead {i}")
    body = (await client.get("/api/v1/knowledge", headers=admin_headers)).json()
    row = next(a for a in body["items"] if a["source"] == "resolved_issue")
    assert row["learning_status"] == "in_use"

    for i in range(5):
        await _confirm(session_factory, admin_user.org_id, symptom=f"still broken {i}",
                       success=False)
    body = (await client.get("/api/v1/knowledge", headers=admin_headers)).json()
    row = next(a for a in body["items"] if a["source"] == "resolved_issue")
    assert row["learning_status"] == "paused"


async def test_a_hand_written_article_is_never_labelled_as_learned(client, admin_headers):
    await client.post("/api/v1/knowledge",
                      json={"title": "VPN", "content": "Open GlobalConnect."},
                      headers=admin_headers)
    body = (await client.get("/api/v1/knowledge", headers=admin_headers)).json()
    assert body["items"][0]["learning_status"] == "authored"


async def test_staff_can_delete_a_learned_article(client, admin_headers, admin_user,
                                                  session_factory):
    """The escape hatch. If ASTRA learns something wrong, a technician must be able to
    simply remove it — without that, automatic learning is a one-way door."""
    await _confirm(session_factory, admin_user.org_id, symptom="outlook nonsense")
    body = (await client.get("/api/v1/knowledge", headers=admin_headers)).json()
    article_id = body["items"][0]["id"]

    resp = await client.delete(f"/api/v1/knowledge/{article_id}", headers=admin_headers)
    assert resp.status_code == 204
    assert (await client.get("/api/v1/knowledge", headers=admin_headers)).json()["items"] == []


def test_topic_key_stays_within_the_column():
    key = learning.topic_key("restart_application", {"process_name": "x" * 200})
    assert len(key) <= 50
