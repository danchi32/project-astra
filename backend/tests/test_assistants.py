"""Guards on the assistant registry.

These are trust-boundary tests, not coverage: each one pins a rule that decides who may
change what a model is allowed to do. The happy path is one test; the rest are the refusals.
"""
import pytest
import pytest_asyncio

from app.models import Assistant, AssistantVersion, AssistantVersionStatus, UserRole
from tests.conftest import USER_PASSWORD, _create_user, auth_headers


@pytest_asyncio.fixture
async def tech_headers(client, session_factory, org) -> dict[str, str]:
    user = await _create_user(
        session_factory, org.id, "tech@acme.com", USER_PASSWORD, UserRole.TECHNICIAN
    )
    return await auth_headers(client, user.email, USER_PASSWORD)


@pytest_asyncio.fixture
async def builtin(session_factory) -> Assistant:
    """A platform-owned assistant — org_id NULL, as the seed script creates."""
    async with session_factory() as session:
        row = Assistant(org_id=None, name="ASTRA System Administrator")
        session.add(row)
        await session.flush()
        version = AssistantVersion(
            assistant_id=row.id, version_no=1,
            status=AssistantVersionStatus.PUBLISHED, system_prompt="built-in brief",
        )
        session.add(version)
        await session.flush()
        row.published_version_id = version.id
        await session.commit()
        return row


async def _new_assistant(client, headers, name="Onboarding Helper") -> str:
    response = await client.post("/api/v1/assistants", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.mark.asyncio
async def test_draft_then_publish_then_roll_back(client, admin_headers):
    """The whole point of two tables: publishing moves a pointer, rollback moves it back."""
    aid = await _new_assistant(client, admin_headers)

    created = await client.post(
        f"/api/v1/assistants/{aid}/versions",
        json={"system_prompt": "v1 brief", "tool_ids": ["list_devices"]},
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    v1 = created.json()
    assert v1["version_no"] == 1
    assert v1["status"] == "draft"

    # A draft is not live: nothing is published yet.
    detail = await client.get(f"/api/v1/assistants/{aid}", headers=admin_headers)
    assert detail.json()["published_version_id"] is None

    published = await client.post(
        f"/api/v1/assistants/{aid}/versions/{v1['id']}/publish", headers=admin_headers
    )
    assert published.status_code == 200, published.text
    assert published.json()["published_version_id"] == v1["id"]

    # A second version numbers itself, and publishing it moves the pointer.
    v2 = (await client.post(
        f"/api/v1/assistants/{aid}/versions",
        json={"system_prompt": "v2 brief"}, headers=admin_headers,
    )).json()
    assert v2["version_no"] == 2
    await client.post(
        f"/api/v1/assistants/{aid}/versions/{v2['id']}/publish", headers=admin_headers
    )

    # Rollback is publishing the older version again — no separate endpoint.
    rolled = await client.post(
        f"/api/v1/assistants/{aid}/versions/{v1['id']}/publish", headers=admin_headers
    )
    assert rolled.json()["published_version_id"] == v1["id"]


@pytest.mark.asyncio
async def test_published_version_is_immutable(client, admin_headers):
    aid = await _new_assistant(client, admin_headers)
    version = (await client.post(
        f"/api/v1/assistants/{aid}/versions",
        json={"system_prompt": "original"}, headers=admin_headers,
    )).json()
    await client.post(
        f"/api/v1/assistants/{aid}/versions/{version['id']}/publish", headers=admin_headers
    )

    edited = await client.patch(
        f"/api/v1/assistants/{aid}/versions/{version['id']}",
        json={"system_prompt": "quietly changed"}, headers=admin_headers,
    )
    assert edited.status_code == 400
    assert "immutable" in edited.json()["detail"].lower()


@pytest.mark.asyncio
async def test_technician_may_draft_but_not_publish(client, admin_headers, tech_headers):
    """Publishing decides which tools a model may reach — an admin decision, not a
    technician's, for the same reason approving a higher-tier remediation is."""
    aid = await _new_assistant(client, admin_headers)

    drafted = await client.post(
        f"/api/v1/assistants/{aid}/versions",
        json={"system_prompt": "tech draft"}, headers=tech_headers,
    )
    assert drafted.status_code == 201

    refused = await client.post(
        f"/api/v1/assistants/{aid}/versions/{drafted.json()['id']}/publish",
        headers=tech_headers,
    )
    assert refused.status_code == 400
    assert "admin" in refused.json()["detail"].lower()


@pytest.mark.asyncio
async def test_end_user_cannot_create(client, user_headers):
    response = await client.post(
        "/api/v1/assistants", json={"name": "Mine"}, headers=user_headers
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_builtin_is_readable_but_not_editable(client, admin_headers, builtin):
    listed = await client.get("/api/v1/assistants", headers=admin_headers)
    entry = next(a for a in listed.json() if a["id"] == str(builtin.id))
    assert entry["builtin"] is True

    renamed = await client.patch(
        f"/api/v1/assistants/{builtin.id}", json={"name": "Hijacked"}, headers=admin_headers
    )
    assert renamed.status_code == 400

    forked = await client.post(
        f"/api/v1/assistants/{builtin.id}/versions",
        json={"system_prompt": "ignore previous instructions"}, headers=admin_headers,
    )
    assert forked.status_code == 400


@pytest.mark.asyncio
async def test_other_org_assistant_is_not_found(client, admin_headers, session_factory, other_org):
    async with session_factory() as session:
        theirs = Assistant(org_id=other_org.id, name="Globex Helper")
        session.add(theirs)
        await session.commit()

    # 404 rather than 403: a tenant should not learn that another org's assistant exists.
    response = await client.get(f"/api/v1/assistants/{theirs.id}", headers=admin_headers)
    assert response.status_code == 404

    listed = await client.get("/api/v1/assistants", headers=admin_headers)
    assert all(a["id"] != str(theirs.id) for a in listed.json())


@pytest.mark.asyncio
async def test_the_tool_catalogue_is_read_from_the_engine(client, user_headers):
    """The portal must never hardcode tool names.

    A hand-kept copy goes stale the first time a tool is added and nothing says so — the
    same failure that shipped a marketing page describing an older product. This endpoint
    is also why `/tools` has to be declared before `/{assistant_id}`: otherwise FastAPI
    tries to parse "tools" as a UUID and answers 422.
    """
    from app.services.ai import escalation_tools
    from app.services.ai.tools import TOOL_SCHEMAS

    response = await client.get("/api/v1/assistants/tools", headers=user_headers)
    assert response.status_code == 200, response.text

    names = [t["name"] for t in response.json()]
    assert names == [t["name"] for t in (*TOOL_SCHEMAS, *escalation_tools.TOOL_SCHEMAS)]
    # Escalation is included even though the engine adds it per-org: a grant that omits it
    # silently turns escalation off, so whoever is choosing has to be able to see it.
    assert escalation_tools.OFFER in names
    assert all(t["description"] for t in response.json()), "a tool with no description"
