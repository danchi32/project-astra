"""Knowledge base tests: CRUD, semantic search, org isolation, and the AI grounding
its answer in a matching article via the search_knowledge_base tool."""


async def _add_article(client, admin_headers, title, content):
    resp = await client.post(
        "/api/v1/knowledge", json={"title": title, "content": content}, headers=admin_headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _enroll(client, admin_headers):
    tok = await client.post(
        "/api/v1/devices/enrollment-tokens", json={"name": "kb"}, headers=admin_headers
    )
    enroll = await client.post(
        "/api/v1/agent/enroll",
        json={
            "enrollment_token": tok.json()["token"],
            "hostname": "KB-PC",
            "machine_id": "kb-pc",
            "os_version": "Windows 11",
            "agent_version": "0.1.0",
        },
    )
    return {"Authorization": f"Bearer {enroll.json()['device_token']}"}


async def test_staff_can_add_and_list_articles(client, admin_headers):
    await _add_article(client, admin_headers, "Reset your password",
                       "Go to portal.acme.com, click 'Forgot password', follow the email link.")
    listing = await client.get("/api/v1/knowledge", headers=admin_headers)
    assert listing.status_code == 200
    titles = [a["title"] for a in listing.json()]
    assert "Reset your password" in titles


async def test_regular_user_cannot_add_article(client, user_headers):
    resp = await client.post(
        "/api/v1/knowledge", json={"title": "x", "content": "y"}, headers=user_headers
    )
    assert resp.status_code == 403


async def test_regular_user_can_read_articles(client, admin_headers, user_headers):
    await _add_article(client, admin_headers, "VPN setup", "Install GlobalConnect and sign in.")
    resp = await client.get("/api/v1/knowledge", headers=user_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_delete_article(client, admin_headers):
    article = await _add_article(client, admin_headers, "Temp", "delete me")
    resp = await client.delete(f"/api/v1/knowledge/{article['id']}", headers=admin_headers)
    assert resp.status_code == 204
    listing = await client.get("/api/v1/knowledge", headers=admin_headers)
    assert listing.json() == []


async def test_semantic_search_finds_relevant_article(session_factory, admin_user):
    from app.services.ai.knowledge import KnowledgeBaseService

    async with session_factory() as session:
        svc = KnowledgeBaseService(session)
        await svc.create(org_id=admin_user.org_id, title="How to reset your password",
                         content="Use the self-service portal to reset your password.")
        await svc.create(org_id=admin_user.org_id, title="Connecting to the VPN",
                         content="Open GlobalConnect and authenticate with MFA.")
        results = await svc.search(org_id=admin_user.org_id, query="i forgot my password")
    assert results, "expected at least one match"
    assert results[0].title == "How to reset your password"


async def test_ai_grounds_answer_in_knowledge_base(client, admin_headers):
    # Author an article, then have the device chat ask a how-to question.
    await _add_article(
        client, admin_headers, "How to connect to the office WiFi",
        "Select ACME-CORP, then sign in with your email and the WiFi password from IT.",
    )
    device_headers = await _enroll(client, admin_headers)
    resp = await client.post(
        "/api/v1/agent/chat",
        json={"content": "how do I connect to the wifi?"},
        headers=device_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    trail = body["tool_trail"]
    assert any(step["tool"] == "search_knowledge_base" for step in trail)
    # The AI's answer is grounded in the article it found.
    assert "knowledge base" in body["reply"].lower() or "ACME-CORP" in body["reply"]


async def test_knowledge_is_org_scoped(client, admin_headers, other_org, session_factory):
    from app.services.ai.knowledge import KnowledgeBaseService

    await _add_article(client, admin_headers, "Secret runbook", "org A only content")
    async with session_factory() as session:
        results = await KnowledgeBaseService(session).search(
            org_id=other_org.id, query="secret runbook"
        )
    assert results == []  # another org cannot see this org's articles
