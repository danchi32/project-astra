"""Billing identity and invoice history.

The tenancy tests here matter more than the CRUD ones. A billing profile carries a
customer's legal name, address and tax number, and an invoice carries what they paid — both
are exactly the sort of thing that must never be reachable by guessing an id from another
organisation.
"""
import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.models import Invoice, Organization, User
from app.models.base import utcnow
from app.services.invites import InviteService
from tests.conftest import USER_PASSWORD


async def _issue_invite(session_factory) -> str:
    async with session_factory() as session:
        _, raw = await InviteService(session).create(note="billing-test", expires_in_days=30)
    return raw


async def _operator_headers(client, session_factory, email="billops@console.com"):
    """A platform admin, built the same way the console tests build one — there is no shared
    fixture for it, and inventing a second way to mint an operator is how the two drift."""
    reg = await client.post("/api/v1/auth/register", json={
        "invite_code": await _issue_invite(session_factory),
        "organization_name": "Bill Ops Co", "admin_name": "Ops",
        "admin_email": email, "admin_password": USER_PASSWORD,
    })
    async with session_factory() as s:
        u = (await s.execute(select(User).where(User.email == email))).scalar_one()
        u.is_platform_admin = True
        await s.commit()
    return {"Authorization": f"Bearer {reg.json()['access_token']}"}


async def _invoice(session_factory, org_id, number, *, status="paid", issued=None, total=9900):
    async with session_factory() as session:
        session.add(Invoice(
            org_id=org_id, number=number,
            issued_on=issued or date(2026, 7, 1),
            period_start=date(2026, 7, 1), period_end=date(2026, 7, 31),
            plan="expert", seats=10, currency="USD",
            subtotal_cents=total, tax_cents=0, discount_cents=0, total_cents=total,
            status=status, provider="razorpay", transaction_id=f"txn-{number}",
            payment_method="card",
        ))
        await session.commit()


# ── Profile ────────────────────────────────────────────────────────────────


async def test_profile_starts_empty_and_incomplete(client, admin_headers):
    body = (await client.get("/api/v1/billing/profile", headers=admin_headers)).json()
    assert body["legal_name"] is None
    # `complete` drives whether an invoice can be raised at all, so it must not read true
    # for a profile nobody has filled in.
    assert body["complete"] is False


async def test_admin_can_save_and_it_becomes_complete(client, admin_headers):
    resp = await client.patch(
        "/api/v1/billing/profile",
        json={
            "legal_name": "Acme Technologies Pvt Ltd",
            "billing_email": "ap@acme.com",
            "address_line1": "12 Residency Road",
            "city": "Bengaluru",
            "country_code": "in",
            "tax_id_label": "GSTIN",
            "tax_id": "29ABCDE1234F1Z5",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Normalised on the way in, so "in" and "IN" can't become two countries in a tax report.
    assert body["country_code"] == "IN"
    assert body["complete"] is True


async def test_a_partial_save_keeps_what_was_there(client, admin_headers):
    """Finance fills this in over several sittings. A form that posts only the field it
    edited must not blank the rest."""
    await client.patch(
        "/api/v1/billing/profile",
        json={"legal_name": "Acme Ltd", "city": "Bengaluru"}, headers=admin_headers,
    )
    await client.patch(
        "/api/v1/billing/profile", json={"tax_id": "29ABCDE1234F1Z5"}, headers=admin_headers,
    )
    body = (await client.get("/api/v1/billing/profile", headers=admin_headers)).json()
    assert body["legal_name"] == "Acme Ltd"
    assert body["city"] == "Bengaluru"
    assert body["tax_id"] == "29ABCDE1234F1Z5"


async def test_a_regular_user_cannot_edit_it(client, user_headers):
    """Readable by anyone in the org — they may need the billing contact — but only an admin
    changes the legal identity the invoice is raised against."""
    assert (await client.get("/api/v1/billing/profile", headers=user_headers)).status_code == 200
    resp = await client.patch(
        "/api/v1/billing/profile", json={"legal_name": "Hijacked"}, headers=user_headers,
    )
    assert resp.status_code == 403


async def test_a_bad_country_code_is_rejected(client, admin_headers):
    resp = await client.patch(
        "/api/v1/billing/profile", json={"country_code": "India"}, headers=admin_headers,
    )
    assert resp.status_code == 422


# ── Invoices ───────────────────────────────────────────────────────────────


async def test_invoices_are_paged_and_filtered(client, admin_headers, admin_user, session_factory):
    for i in range(12):
        await _invoice(
            session_factory, admin_user.org_id, f"AST-{i:04d}",
            status="paid" if i % 2 else "failed",
            issued=date(2026, 7, 1) + timedelta(days=i),
        )

    page1 = (await client.get(
        "/api/v1/billing/invoices?page=1&page_size=5", headers=admin_headers
    )).json()
    assert page1["total"] == 12
    assert len(page1["items"]) == 5

    failed = (await client.get(
        "/api/v1/billing/invoices?status=failed", headers=admin_headers
    )).json()
    assert failed["total"] == 6
    assert {i["status"] for i in failed["items"]} == {"failed"}

    ranged = (await client.get(
        "/api/v1/billing/invoices?issued_from=2026-07-05&issued_to=2026-07-08",
        headers=admin_headers,
    )).json()
    assert ranged["total"] == 4


async def test_invoice_search_matches_number_and_transaction(
    client, admin_headers, admin_user, session_factory
):
    await _invoice(session_factory, admin_user.org_id, "AST-9001")
    body = (await client.get(
        "/api/v1/billing/invoices?q=9001", headers=admin_headers
    )).json()
    assert body["total"] == 1
    assert body["items"][0]["number"] == "AST-9001"


async def test_money_survives_the_round_trip(client, admin_headers, admin_user, session_factory):
    """Minor units, as integers. A float column would lose a paisa somewhere and there is no
    good way to explain that to someone holding a bank statement."""
    await _invoice(session_factory, admin_user.org_id, "AST-CENTS", total=123456)
    body = (await client.get("/api/v1/billing/invoices?q=CENTS", headers=admin_headers)).json()
    assert body["items"][0]["total_cents"] == 123456


# ── Tenancy: the part that must not leak ───────────────────────────────────


async def test_one_org_cannot_see_another_orgs_invoices(
    client, admin_headers, admin_user, session_factory
):
    async with session_factory() as session:
        other = Organization(name="Other Co", plan="expert", updated_at=utcnow())
        session.add(other)
        await session.flush()
        other_id = other.id
        await session.commit()

    await _invoice(session_factory, other_id, "OTHER-0001")
    await _invoice(session_factory, admin_user.org_id, "MINE-0001")

    body = (await client.get("/api/v1/billing/invoices", headers=admin_headers)).json()
    numbers = {i["number"] for i in body["items"]}
    assert numbers == {"MINE-0001"}


async def test_fetching_another_orgs_invoice_by_id_is_a_404_not_a_403(
    client, admin_headers, session_factory
):
    """404, deliberately. A 403 would confirm the id is real, which is a slow way of
    enumerating another customer's billing history."""
    async with session_factory() as session:
        other = Organization(name="Other Co 2", plan="expert", updated_at=utcnow())
        session.add(other)
        await session.flush()
        other_id = other.id
        await session.commit()

    await _invoice(session_factory, other_id, "SNOOP-0001")

    async with session_factory() as session:
        from sqlalchemy import select
        inv_id = (await session.execute(
            select(Invoice.id).where(Invoice.number == "SNOOP-0001")
        )).scalar_one()

    resp = await client.get(f"/api/v1/billing/invoices/{inv_id}", headers=admin_headers)
    assert resp.status_code == 404


async def test_a_random_invoice_id_is_a_404(client, admin_headers):
    resp = await client.get(f"/api/v1/billing/invoices/{uuid.uuid4()}", headers=admin_headers)
    assert resp.status_code == 404


# ── Operator console ───────────────────────────────────────────────────────


async def test_platform_orgs_are_paged_and_searchable(client, session_factory):
    platform_headers = await _operator_headers(client, session_factory, 'p1@console.com')
    async with session_factory() as session:
        for i in range(8):
            session.add(Organization(
                name=f"Paged Co {i:02d}", plan="expert", updated_at=utcnow(),
                email_domain=f"paged{i:02d}.com",
            ))
        await session.commit()

    page = (await client.get(
        "/api/v1/platform/organizations?page=1&page_size=5", headers=platform_headers
    )).json()
    assert len(page["items"]) == 5
    assert page["total"] >= 8
    assert page["pages"] >= 2

    found = (await client.get(
        "/api/v1/platform/organizations?q=paged03", headers=platform_headers
    )).json()
    # Matched on the domain, which is how an operator usually recognises an account.
    assert found["total"] == 1
    assert found["items"][0]["name"] == "Paged Co 03"


async def test_platform_org_counts_are_for_the_page_only(client, session_factory):
    """The counts used to come from aggregating every user and device in the system to label
    whatever rows were shown. Correctness is the same; the cost is not."""
    platform_headers = await _operator_headers(client, session_factory, "p2@console.com")
    page = (await client.get(
        "/api/v1/platform/organizations?page_size=2", headers=platform_headers
    )).json()
    assert len(page["items"]) <= 2
    for row in page["items"]:
        assert "user_count" in row and "device_count" in row


async def test_operator_sees_every_orgs_invoices(client, admin_user, session_factory):
    platform_headers = await _operator_headers(client, session_factory, 'p3@console.com')
    async with session_factory() as session:
        other = Organization(name="Cross Co", plan="expert", updated_at=utcnow())
        session.add(other)
        await session.flush()
        other_id = other.id
        await session.commit()

    await _invoice(session_factory, other_id, "CROSS-0001")
    await _invoice(session_factory, admin_user.org_id, "CROSS-0002")

    body = (await client.get("/api/v1/platform/invoices", headers=platform_headers)).json()
    numbers = {i["number"] for i in body["items"]}
    assert {"CROSS-0001", "CROSS-0002"} <= numbers
    # The operator's list has an organization column, resolved for the page.
    assert all(i["org_name"] for i in body["items"])


async def test_a_normal_admin_cannot_reach_the_operator_billing_view(client, admin_headers):
    assert (await client.get("/api/v1/platform/invoices", headers=admin_headers)).status_code == 403
