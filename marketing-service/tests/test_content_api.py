"""The content endpoints.

The gate is proven at the service layer in test_content_gate.py. This proves the HTTP
surface enforces the same thing, because HTTP is what n8n and the approval desk actually
call — a gate that holds in Python and leaks through a route protects nothing.
"""
import pytest

from app.models.content import ContentChannel, ContentStatus
from app.services.content import ContentService

TRUE_COPY = (
    "ASTRA gathers endpoint evidence before it proposes a fix. Remediations are tiered "
    "and the tier is enforced server-side."
)


@pytest.fixture
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
async def item(session_factory):
    """Created through the service — drafting needs an API key the suite does not have."""
    async with session_factory() as session:
        created = await ContentService(session).create(
            channel=ContentChannel.LINKEDIN, body=TRUE_COPY, actor="test",
        )
        return created


# ── Everything is behind the token ────────────────────────────────────────────

async def test_listing_content_requires_the_admin_token(client):
    """Unpublished copy, and an event log naming who approved what. None of it is public."""
    assert (await client.get("/api/v1/content")).status_code == 401


async def test_drafting_requires_the_admin_token(client):
    response = await client.post("/api/v1/content/draft", json={
        "channel": "linkedin", "brief": "Explain the approval tiers to an IT lead."
    })
    assert response.status_code == 401


# ── The gate, over HTTP ───────────────────────────────────────────────────────

async def test_publishing_unapproved_content_is_refused(client, auth, item):
    response = await client.post(
        f"/api/v1/content/{item.id}/published", headers=auth,
        json={"actor": "publisher"},
    )

    assert response.status_code == 409
    assert "approved" in response.json()["detail"]


async def test_publishing_after_a_revision_is_refused(client, auth, item, session_factory):
    """The sequence a status column would allow: approve, edit, publish.

    Revised through the service rather than the endpoint, because the revise endpoint
    calls the model and the suite has no API key. What is under test is the gate, not the
    route that reaches it.
    """
    await client.post(f"/api/v1/content/{item.id}/submit", headers=auth,
                      json={"actor": "agent"})
    detail = (await client.get(f"/api/v1/content/{item.id}", headers=auth)).json()
    await client.post(f"/api/v1/content/{item.id}/approve", headers=auth,
                      json={"actor": "danish", "version_id": detail["current_version_id"]})

    async with session_factory() as session:
        await ContentService(session).revise(
            item.id, body=TRUE_COPY + " One more line nobody reviewed.",
            actor="agent", reason="tweak",
        )

    response = await client.post(f"/api/v1/content/{item.id}/published", headers=auth,
                                 json={"actor": "publisher"})
    assert response.status_code == 409
    # Refused on status, not on the version mismatch: revising clears the approval AND
    # drops back to DRAFT, so the first check catches it. The version check behind it is
    # defence in depth — see test_content_gate for the case that reaches it.
    assert "only approved content" in response.json()["detail"]


async def test_the_full_path_to_published_works(client, auth, item):
    await client.post(f"/api/v1/content/{item.id}/submit", headers=auth,
                      json={"actor": "agent"})
    detail = (await client.get(f"/api/v1/content/{item.id}", headers=auth)).json()
    assert detail["status"] == ContentStatus.IN_REVIEW

    approved = await client.post(
        f"/api/v1/content/{item.id}/approve", headers=auth,
        json={"actor": "danish", "version_id": detail["current_version_id"]},
    )
    assert approved.status_code == 200
    assert approved.json()["approved_by"] == "danish"

    published = await client.post(
        f"/api/v1/content/{item.id}/published", headers=auth,
        json={"actor": "publisher", "url": "https://linkedin.com/post/1"},
    )
    assert published.status_code == 200
    assert published.json()["status"] == ContentStatus.PUBLISHED
    assert published.json()["published_url"] == "https://linkedin.com/post/1"


async def test_approving_a_version_that_is_not_current_is_refused(client, auth, item):
    await client.post(f"/api/v1/content/{item.id}/submit", headers=auth,
                      json={"actor": "agent"})
    response = await client.post(
        f"/api/v1/content/{item.id}/approve", headers=auth,
        json={"actor": "danish", "version_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 409


# ── Reading ───────────────────────────────────────────────────────────────────

async def test_detail_carries_the_versions_and_the_trail(client, auth, item):
    detail = (await client.get(f"/api/v1/content/{item.id}", headers=auth)).json()

    assert len(detail["versions"]) == 1
    assert detail["versions"][0]["version_number"] == 1
    assert detail["versions"][0]["check_result"] is not None
    assert {e["event"] for e in detail["events"]} >= {"created", "checked"}


async def test_drafting_without_a_key_is_a_503_not_a_crash(client, auth):
    response = await client.post(
        "/api/v1/content/draft", headers=auth,
        json={"channel": "linkedin", "brief": "Explain the approval tiers to an IT lead."},
    )
    assert response.status_code == 503
    assert "ANTHROPIC" in response.json()["detail"]


async def test_unknown_content_is_a_404(client, auth):
    response = await client.get(
        "/api/v1/content/00000000-0000-0000-0000-000000000000", headers=auth
    )
    assert response.status_code == 404
