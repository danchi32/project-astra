"""ASTRA's customer-facing support documentation.

The isolation tests matter most. This endpoint serves one organization content that was
written outside it, which is exactly the shape of a tenant leak — so "only global, only
published" is asserted from both directions.
"""
import uuid

from sqlalchemy import select

from app.models import KnowledgeArticle, KnowledgeSource, User, UserRole
from app.models.base import utcnow
from tests.conftest import ADMIN_PASSWORD, USER_PASSWORD, auth_headers


def _article(*, org_id=None, title="Agent will not install", content="Body text",
             published=True, category="installation", code="ASTRA-1001"):
    return KnowledgeArticle(
        org_id=org_id, title=title, content=content,
        embedding=[0.0] * 8, embedding_model="hash-256",
        source=KnowledgeSource.MANUAL,
        published_at=utcnow() if published else None,
        help_category=category, error_code=code,
    )


async def test_only_global_published_articles_are_served(client, session_factory, org, admin_user):
    """An organization's own runbook must never appear in ASTRA's help centre."""
    async with session_factory() as s:
        s.add(_article(title="ASTRA install fails with 0x80070005", code="0x80070005"))
        s.add(_article(org_id=org.id, title="Our internal VPN runbook", code="INTERNAL-9"))
        s.add(_article(title="Unfinished draft", published=False, code="DRAFT-1"))
        await s.commit()

    headers = await auth_headers(client, admin_user.email, ADMIN_PASSWORD)
    response = await client.get("/api/v1/help/articles", headers=headers)
    assert response.status_code == 200, response.text

    titles = [a["title"] for a in response.json()]
    assert titles == ["ASTRA install fails with 0x80070005"]
    assert "Our internal VPN runbook" not in response.text
    assert "Unfinished draft" not in response.text


async def test_another_orgs_article_is_not_reachable_by_id(
    client, session_factory, org, other_org, admin_user
):
    """Guessing an id must not work either — the list filter is not the only gate."""
    async with session_factory() as s:
        private = _article(org_id=other_org.id, title="Globex private runbook")
        s.add(private)
        await s.commit()
        private_id = private.id

    headers = await auth_headers(client, admin_user.email, ADMIN_PASSWORD)
    response = await client.get(f"/api/v1/help/articles/{private_id}", headers=headers)
    assert response.status_code == 404, response.text
    assert "Globex" not in response.text


async def test_unpublished_article_is_not_reachable_by_id(client, session_factory, admin_user):
    async with session_factory() as s:
        draft = _article(title="Draft: agent proxy setup", published=False)
        s.add(draft)
        await s.commit()
        draft_id = draft.id

    headers = await auth_headers(client, admin_user.email, ADMIN_PASSWORD)
    response = await client.get(f"/api/v1/help/articles/{draft_id}", headers=headers)
    assert response.status_code == 404


async def test_error_code_lookup_ignores_case(client, session_factory, admin_user):
    """People quote codes back in whatever case they see them in."""
    async with session_factory() as s:
        s.add(_article(title="Access denied during install", code="0x80070005"))
        s.add(_article(title="Something else", code="ASTRA-2002"))
        await s.commit()

    headers = await auth_headers(client, admin_user.email, ADMIN_PASSWORD)
    response = await client.get(
        "/api/v1/help/articles", params={"error_code": "  0X80070005 "}, headers=headers
    )
    assert [a["title"] for a in response.json()] == ["Access denied during install"]


async def test_every_role_can_read_support_content(client, session_factory, regular_user):
    """The person who cannot install the agent is usually not an administrator."""
    async with session_factory() as s:
        s.add(_article(title="Installer blocked by antivirus"))
        await s.commit()

    headers = await auth_headers(client, regular_user.email, USER_PASSWORD)
    response = await client.get("/api/v1/help/articles", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_help_centre_requires_authentication(client):
    response = await client.get("/api/v1/help/articles")
    assert response.status_code == 401


async def test_categories_report_only_populated_sections(client, session_factory, org, admin_user):
    """An empty section in a browse UI reads as a broken page."""
    async with session_factory() as s:
        s.add(_article(title="Install A", category="installation"))
        s.add(_article(title="Install B", category="installation"))
        s.add(_article(title="Net A", category="network"))
        s.add(_article(title="Hidden draft", category="billing", published=False))
        s.add(_article(org_id=org.id, title="Org private", category="portal"))
        await s.commit()

    headers = await auth_headers(client, admin_user.email, ADMIN_PASSWORD)
    body = (await client.get("/api/v1/help/categories", headers=headers)).json()

    assert body == {"installation": 2, "network": 1}
    assert "billing" not in body   # only a draft lives there
    assert "portal" not in body    # that one belongs to an organization


async def test_free_text_search_covers_title_body_and_code(client, session_factory, admin_user):
    async with session_factory() as s:
        s.add(_article(title="Proxy configuration", content="Set the WinHTTP proxy", code="ASTRA-3001"))
        s.add(_article(title="Unrelated", content="Nothing to see", code="ASTRA-9999"))
        await s.commit()

    headers = await auth_headers(client, admin_user.email, ADMIN_PASSWORD)

    for query in ("proxy", "winhttp", "3001"):
        found = (await client.get(
            "/api/v1/help/articles", params={"q": query}, headers=headers
        )).json()
        assert [a["title"] for a in found] == ["Proxy configuration"], query


# ── operator authoring ────────────────────────────────────────────────────


async def _platform_admin(client, session_factory, admin_user) -> dict:
    async with session_factory() as s:
        u = (await s.execute(select(User).where(User.id == admin_user.id))).scalar_one()
        u.is_platform_admin = True
        await s.commit()
    return await auth_headers(client, admin_user.email, ADMIN_PASSWORD)


async def test_operator_publishes_an_article_customers_can_read(
    client, session_factory, admin_user
):
    headers = await _platform_admin(client, session_factory, admin_user)

    created = await client.post("/api/v1/platform/knowledge", headers=headers, json={
        "title": "Agent install fails: .NET 8 runtime missing",
        "content": "Install the .NET 8 Desktop Runtime, then re-run the installer.",
        "help_category": "installation",
        "error_code": "ASTRA-1002",
    })
    assert created.status_code == 201, created.text
    assert created.json()["published_at"] is not None

    found = (await client.get(
        "/api/v1/help/articles", params={"error_code": "ASTRA-1002"}, headers=headers
    )).json()
    assert len(found) == 1
    assert found[0]["help_category"] == "installation"


async def test_withdrawing_an_article_removes_it_from_the_help_centre(
    client, session_factory, admin_user
):
    headers = await _platform_admin(client, session_factory, admin_user)
    created = (await client.post("/api/v1/platform/knowledge", headers=headers, json={
        "title": "Temporary notice", "content": "Body", "help_category": "other",
    })).json()

    patched = await client.patch(
        f"/api/v1/platform/knowledge/{created['id']}", headers=headers,
        json={"published": False},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["published_at"] is None

    remaining = (await client.get("/api/v1/help/articles", headers=headers)).json()
    assert remaining == []


async def test_clearing_a_field_differs_from_omitting_it(client, session_factory, admin_user):
    """Sending null removes an error code entered by mistake; omitting it must not."""
    headers = await _platform_admin(client, session_factory, admin_user)
    created = (await client.post("/api/v1/platform/knowledge", headers=headers, json={
        "title": "Article", "content": "Body",
        "help_category": "network", "error_code": "TYPO-1",
    })).json()

    # Omitting error_code leaves it in place.
    after_title_edit = (await client.patch(
        f"/api/v1/platform/knowledge/{created['id']}", headers=headers,
        json={"title": "Article, revised"},
    )).json()
    assert after_title_edit["error_code"] == "TYPO-1"
    assert after_title_edit["title"] == "Article, revised"

    # Sending it as null removes it.
    cleared = (await client.patch(
        f"/api/v1/platform/knowledge/{created['id']}", headers=headers,
        json={"error_code": None},
    )).json()
    assert cleared["error_code"] is None
    assert cleared["help_category"] == "network"   # untouched


async def test_editing_the_body_rebuilds_the_embedding(client, session_factory, admin_user):
    """Otherwise the article stays findable by its old words and invisible under its new."""
    headers = await _platform_admin(client, session_factory, admin_user)
    created = (await client.post("/api/v1/platform/knowledge", headers=headers, json={
        "title": "Printer setup", "content": "Original body",
    })).json()

    async with session_factory() as s:
        before = (await s.execute(
            select(KnowledgeArticle).where(KnowledgeArticle.id == uuid.UUID(created["id"]))
        )).scalar_one().embedding

    await client.patch(f"/api/v1/platform/knowledge/{created['id']}", headers=headers,
                       json={"content": "A completely different explanation of the fix"})

    async with session_factory() as s:
        after = (await s.execute(
            select(KnowledgeArticle).where(KnowledgeArticle.id == uuid.UUID(created["id"]))
        )).scalar_one().embedding

    assert before != after


async def test_authoring_requires_platform_admin(client, session_factory, admin_user):
    """An org admin must not be able to publish to every other customer."""
    headers = await auth_headers(client, admin_user.email, ADMIN_PASSWORD)
    response = await client.post("/api/v1/platform/knowledge", headers=headers, json={
        "title": "Not allowed", "content": "Body",
    })
    assert response.status_code == 403


async def test_operator_cannot_edit_an_organizations_article(
    client, session_factory, org, admin_user
):
    """The PATCH route is for ASTRA's own documentation, not a customer's runbooks."""
    headers = await _platform_admin(client, session_factory, admin_user)
    async with session_factory() as s:
        theirs = _article(org_id=org.id, title="Their runbook")
        s.add(theirs)
        await s.commit()
        theirs_id = theirs.id

    response = await client.patch(
        f"/api/v1/platform/knowledge/{theirs_id}", headers=headers,
        json={"title": "Hijacked"},
    )
    assert response.status_code == 404
