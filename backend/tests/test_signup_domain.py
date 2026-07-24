"""Self-service signup rules: one organisation per corporate email domain (personal/free
providers exempt), and the relaxed 8-character password floor."""
import pytest

from app.core.email_domains import corporate_domain


def _body(org, email, pw="password123"):
    return {"organization_name": org, "admin_name": "Admin", "admin_email": email,
            "admin_password": pw}


async def _register(client, org, email, pw="password123"):
    return await client.post("/api/v1/auth/register", json=_body(org, email, pw))


def test_corporate_domain_helper():
    assert corporate_domain("a@acme.com") == "acme.com"
    assert corporate_domain("A@ACME.COM") == "acme.com"       # case-insensitive
    assert corporate_domain("x@gmail.com") is None            # personal -> exempt
    assert corporate_domain("x@outlook.com") is None
    assert corporate_domain("") is None


async def test_second_signup_from_same_corporate_domain_is_blocked(client):
    first = await _register(client, "Acme Inc", "founder@acme-corp.com")
    assert first.status_code == 201, first.text

    second = await _register(client, "Acme Two", "another@acme-corp.com")
    assert second.status_code == 409, second.text
    assert "already registered" in second.json()["detail"].lower()
    assert "acme-corp.com" in second.json()["detail"]


async def test_personal_domains_can_register_repeatedly(client):
    a = await _register(client, "Personal One", "alice@gmail.com")
    b = await _register(client, "Personal Two", "bob@gmail.com")
    c = await _register(client, "Personal Three", "carol@outlook.com")
    assert a.status_code == 201, a.text
    assert b.status_code == 201, b.text     # same gmail domain, different person -> allowed
    assert c.status_code == 201, c.text


async def test_password_floor_is_eight(client):
    ok = await _register(client, "Eight Co", "admin@eight-co.com", pw="abcd1234")   # 8 chars
    assert ok.status_code == 201, ok.text

    too_short = await _register(client, "Seven Co", "admin@seven-co.com", pw="abc1234")  # 7
    assert too_short.status_code == 422   # pydantic min_length rejects before the service
