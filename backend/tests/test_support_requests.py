"""An organization asking ASTRA for help, and ASTRA answering.

Three things are worth pinning down: who can read a thread, that the diagnostics snapshot
is built from the database rather than from whatever the client claimed, and that the
status moves on its own — a queue where somebody must remember to set the state is a queue
that lies.
"""
import uuid

from sqlalchemy import select

from app.models import (
    Device, Notification, SupportRequest, SupportRequestStatus, User, UserRole,
)
from app.models.base import utcnow
from tests.conftest import ADMIN_PASSWORD, USER_PASSWORD, auth_headers


async def _raise_request(client, headers, subject="Agent will not install", **kw):
    payload = {"subject": subject, "body": "The installer stops at 40%.", **kw}
    response = await client.post("/api/v1/support/requests", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def _operator_headers(client, session_factory, user) -> dict:
    async with session_factory() as s:
        u = (await s.execute(select(User).where(User.id == user.id))).scalar_one()
        u.is_platform_admin = True
        await s.commit()
    password = ADMIN_PASSWORD if user.role is UserRole.ADMIN else USER_PASSWORD
    return await auth_headers(client, user.email, password)


async def test_request_carries_a_server_built_diagnostics_snapshot(
    client, session_factory, org, admin_user
):
    """The point of the form: the fleet explains itself without anyone typing it out."""
    async with session_factory() as s:
        for i in range(3):
            s.add(Device(
                org_id=org.id, hostname=f"pc-{i}", machine_id=f"m-{i}",
                os_version="Windows 11", agent_version="0.8.2" if i else "0.7.1",
                token_hash=f"tok-{i}", last_seen_at=utcnow() if i else None,
            ))
        await s.commit()

    headers = await auth_headers(client, admin_user.email, ADMIN_PASSWORD)
    body = await _raise_request(client, headers)

    diag = body["diagnostics"]
    assert diag["devices_total"] == 3
    assert diag["devices_online"] == 2      # the one with no heartbeat is not online
    assert diag["devices_offline"] == 1
    assert diag["agent_versions"] == {"0.8.2": 2, "0.7.1": 1}
    assert diag["captured_at"]
    # Aggregates only — a support queue has no business holding a device inventory.
    assert "pc-0" not in str(diag)


async def test_client_cannot_forge_diagnostics(client, session_factory, org, admin_user):
    """A ticket that reports whatever the browser claimed can lie about the fleet."""
    headers = await auth_headers(client, admin_user.email, ADMIN_PASSWORD)
    response = await client.post("/api/v1/support/requests", headers=headers, json={
        "subject": "Forged", "body": "Body",
        "diagnostics": {"devices_total": 9999, "plan": "enterprise"},
    })
    assert response.status_code == 201
    assert response.json()["diagnostics"]["devices_total"] == 0


async def test_reference_is_returned_and_unique(client, session_factory, admin_user):
    headers = await auth_headers(client, admin_user.email, ADMIN_PASSWORD)
    first = await _raise_request(client, headers, subject="One")
    second = await _raise_request(client, headers, subject="Two")

    assert first["reference"].startswith("SUP-")
    assert first["reference"] != second["reference"]


async def test_a_regular_user_sees_only_their_own_requests(
    client, session_factory, org, admin_user, regular_user
):
    """A thread can contain anything its author chose to type."""
    admin_headers = await auth_headers(client, admin_user.email, ADMIN_PASSWORD)
    user_headers = await auth_headers(client, regular_user.email, USER_PASSWORD)

    await _raise_request(client, admin_headers, subject="Raised by the admin")
    mine = await _raise_request(client, user_headers, subject="Raised by me")

    listed = (await client.get("/api/v1/support/requests", headers=user_headers)).json()
    assert [r["subject"] for r in listed] == ["Raised by me"]

    # Staff see the whole organization's requests, because they answer for it.
    staff_view = (await client.get("/api/v1/support/requests", headers=admin_headers)).json()
    assert {r["subject"] for r in staff_view} == {"Raised by the admin", "Raised by me"}

    # And the admin's thread is not reachable by id for the regular user.
    admin_thread = [r for r in staff_view if r["subject"] == "Raised by the admin"][0]
    denied = await client.get(
        f"/api/v1/support/requests/{admin_thread['id']}", headers=user_headers
    )
    assert denied.status_code == 404
    assert mine["id"] != admin_thread["id"]


async def test_another_organization_cannot_read_the_thread(
    client, session_factory, org, other_org, admin_user, other_org_user
):
    headers = await auth_headers(client, admin_user.email, ADMIN_PASSWORD)
    raised = await _raise_request(client, headers, subject="Ours")

    theirs = await auth_headers(client, other_org_user.email, USER_PASSWORD)
    response = await client.get(f"/api/v1/support/requests/{raised['id']}", headers=theirs)
    assert response.status_code == 404
    assert "Ours" not in response.text


async def test_customer_cannot_set_urgent(client, session_factory, admin_user):
    """Urgency is the operator's scheduling decision, not the requester's."""
    headers = await auth_headers(client, admin_user.email, ADMIN_PASSWORD)
    body = await _raise_request(client, headers, priority="urgent")
    assert body["priority"] == "high"


async def test_operator_reply_hands_the_thread_back_and_notifies(
    client, session_factory, org, admin_user, regular_user
):
    user_headers = await auth_headers(client, regular_user.email, USER_PASSWORD)
    raised = await _raise_request(client, user_headers)
    assert raised["status"] == "open"

    op_headers = await _operator_headers(client, session_factory, admin_user)
    replied = await client.post(
        f"/api/v1/platform/support-requests/{raised['id']}/replies",
        headers=op_headers, json={"body": "Please run the installer as administrator."},
    )
    assert replied.status_code == 201, replied.text
    thread = replied.json()

    assert thread["status"] == "waiting_customer"
    assert [m["from_operator"] for m in thread["messages"]] == [False, True]

    async with session_factory() as s:
        notes = (await s.execute(
            select(Notification).where(Notification.org_id == org.id)
        )).scalars().all()
    assert any(raised["reference"] in n.title for n in notes)


async def test_customer_reply_reopens_the_thread(
    client, session_factory, org, admin_user, regular_user
):
    """Someone replying to a resolved thread is telling us it was not resolved."""
    user_headers = await auth_headers(client, regular_user.email, USER_PASSWORD)
    raised = await _raise_request(client, user_headers)

    op_headers = await _operator_headers(client, session_factory, admin_user)
    await client.patch(
        f"/api/v1/platform/support-requests/{raised['id']}",
        headers=op_headers, json={"status": "resolved"},
    )

    reopened = await client.post(
        f"/api/v1/support/requests/{raised['id']}/replies",
        headers=user_headers, json={"body": "It is still happening."},
    )
    assert reopened.status_code == 201
    assert reopened.json()["status"] == "open"
    assert reopened.json()["resolved_at"] is None


async def test_operator_queue_orders_by_whose_turn_it_is(
    client, session_factory, org, admin_user, regular_user
):
    user_headers = await auth_headers(client, regular_user.email, USER_PASSWORD)
    waiting = await _raise_request(client, user_headers, subject="Parked on the customer")
    ours = await _raise_request(client, user_headers, subject="Still ours")

    op_headers = await _operator_headers(client, session_factory, admin_user)
    # Answering the first one parks it with the customer.
    await client.post(
        f"/api/v1/platform/support-requests/{waiting['id']}/replies",
        headers=op_headers, json={"body": "Could you send the log?"},
    )

    queue = (await client.get("/api/v1/platform/support-requests", headers=op_headers)).json()
    subjects = [r["subject"] for r in queue["requests"]]
    assert subjects.index("Still ours") < subjects.index("Parked on the customer")
    assert queue["counts_by_status"]["open"] == 1
    assert queue["counts_by_status"]["waiting_customer"] == 1
    assert queue["requests"][0]["org_name"] == org.name
    assert ours["id"]


async def test_queue_requires_platform_admin(client, session_factory, admin_user):
    """An org admin must not see other customers' support threads."""
    headers = await auth_headers(client, admin_user.email, ADMIN_PASSWORD)
    response = await client.get("/api/v1/platform/support-requests", headers=headers)
    assert response.status_code == 403


async def test_customer_cannot_set_their_own_status(client, session_factory, admin_user):
    """There is no customer-facing status route — they move a thread by replying."""
    headers = await auth_headers(client, admin_user.email, ADMIN_PASSWORD)
    raised = await _raise_request(client, headers)
    response = await client.patch(
        f"/api/v1/support/requests/{raised['id']}", headers=headers,
        json={"status": "resolved"},
    )
    assert response.status_code in (404, 405)


async def test_support_requests_require_authentication(client):
    assert (await client.get("/api/v1/support/requests")).status_code == 401
    assert (await client.post("/api/v1/support/requests", json={
        "subject": "x", "body": "y"
    })).status_code == 401


async def test_creating_a_request_is_audited(client, session_factory, org, admin_user):
    from app.models import AuditLog

    headers = await auth_headers(client, admin_user.email, ADMIN_PASSWORD)
    raised = await _raise_request(client, headers)

    async with session_factory() as s:
        entries = (await s.execute(
            select(AuditLog).where(AuditLog.action == "support_request.create")
        )).scalars().all()
    assert len(entries) == 1
    assert entries[0].target_id == raised["id"]
    assert entries[0].org_id == org.id


async def test_unknown_request_id_is_not_found(client, session_factory, admin_user):
    headers = await auth_headers(client, admin_user.email, ADMIN_PASSWORD)
    response = await client.get(
        f"/api/v1/support/requests/{uuid.uuid4()}", headers=headers
    )
    assert response.status_code == 404


async def test_thread_shows_who_wrote_each_message(
    client, session_factory, admin_user, regular_user
):
    user_headers = await auth_headers(client, regular_user.email, USER_PASSWORD)
    raised = await _raise_request(client, user_headers)

    op_headers = await _operator_headers(client, session_factory, admin_user)
    thread = (await client.post(
        f"/api/v1/platform/support-requests/{raised['id']}/replies",
        headers=op_headers, json={"body": "Looking into it."},
    )).json()

    authors = {(m["from_operator"], m["author_email"]) for m in thread["messages"]}
    assert (False, regular_user.email) in authors
    assert (True, admin_user.email) in authors


async def test_stored_request_keeps_its_snapshot_after_the_fleet_changes(
    client, session_factory, org, admin_user
):
    """A thread has to keep explaining itself a week later."""
    headers = await auth_headers(client, admin_user.email, ADMIN_PASSWORD)
    raised = await _raise_request(client, headers)
    assert raised["diagnostics"]["devices_total"] == 0

    async with session_factory() as s:
        s.add(Device(
            org_id=org.id, hostname="later", machine_id="later", os_version="Windows 11",
            agent_version="0.8.2", token_hash="later-tok", last_seen_at=utcnow(),
        ))
        await s.commit()

    reread = (await client.get(
        f"/api/v1/support/requests/{raised['id']}", headers=headers
    )).json()
    assert reread["diagnostics"]["devices_total"] == 0   # the snapshot, not a live count

    async with session_factory() as s:
        stored = (await s.execute(
            select(SupportRequest).where(SupportRequest.id == uuid.UUID(raised["id"]))
        )).scalar_one()
    assert stored.status is SupportRequestStatus.OPEN
