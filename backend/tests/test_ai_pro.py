"""Pro-AI entitlement: the operator toggles it per org, and it gates escalation to the
real Claude LLM (Basic orgs stay on the built-in engine)."""
from app.core.config import get_settings
from app.models import Organization
from app.services.ai.provider import AnthropicProvider, StubProvider
from app.services.conversations import ConversationService
from tests.test_platform_console import _operator, _register_org


async def test_ai_pro_gates_the_real_llm(session_factory, monkeypatch):
    # Force past the built-in fast paths, and pretend a platform Anthropic key is set.
    monkeypatch.setattr(StubProvider, "can_handle", lambda self, **kw: False)
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-ant-test")

    async with session_factory() as session:
        basic = Organization(name="Basic Co", ai_pro=False)
        pro = Organization(name="Pro Co", ai_pro=True)
        session.add_all([basic, pro])
        await session.commit()
        await session.refresh(basic)
        await session.refresh(pro)

        svc = ConversationService(session)
        prov_basic, _ = await svc._route(basic.id, "some obscure question xyz", None)
        prov_pro, _ = await svc._route(pro.id, "some obscure question xyz", None)

    assert isinstance(prov_basic, StubProvider)       # Basic → built-in engine only
    assert isinstance(prov_pro, AnthropicProvider)    # Pro → real Claude


async def test_no_key_means_no_real_llm_even_for_pro(session_factory, monkeypatch):
    monkeypatch.setattr(StubProvider, "can_handle", lambda self, **kw: False)
    monkeypatch.setattr(get_settings(), "anthropic_api_key", None)

    async with session_factory() as session:
        pro = Organization(name="Pro NoKey", ai_pro=True)
        session.add(pro)
        await session.commit()
        await session.refresh(pro)
        prov, _ = await ConversationService(session)._route(pro.id, "obscure xyz", None)
    assert isinstance(prov, StubProvider)


async def test_operator_toggles_ai_pro(client, session_factory):
    headers = await _operator(client, session_factory, org="AIPro Ops", email="op@aipro.com")
    await _register_org(client, session_factory, "AIPro Cust", "a@aipro.com")
    orgs = (await client.get("/api/v1/platform/organizations", headers=headers)).json()
    org = next(o for o in orgs if o["name"] == "AIPro Cust")
    assert org["ai_pro"] is False  # Basic by default

    on = await client.patch(f"/api/v1/platform/organizations/{org['id']}",
                            json={"ai_pro": True}, headers=headers)
    assert on.status_code == 200, on.text
    assert on.json()["ai_pro"] is True

    off = await client.patch(f"/api/v1/platform/organizations/{org['id']}",
                             json={"ai_pro": False}, headers=headers)
    assert off.json()["ai_pro"] is False
