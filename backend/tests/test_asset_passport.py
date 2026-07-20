"""Device passport: lifecycle events are recorded and the passport summarizes them."""
import uuid

from sqlalchemy import select

from app.models import Asset


async def _create(client, headers, **overrides):
    payload = {"name": "Dell Latitude 5540", "category": "laptop", "status": "in_use"}
    payload.update(overrides)
    return await client.post("/api/v1/assets", json=payload, headers=headers)


async def test_passport_records_create_and_status_changes(client, admin_headers):
    created = await _create(client, admin_headers, status="in_use", location="HQ")
    asset_id = created.json()["id"]

    # in_use -> in_repair -> in_storage
    await client.patch(f"/api/v1/assets/{asset_id}", json={"status": "in_repair"}, headers=admin_headers)
    await client.patch(f"/api/v1/assets/{asset_id}", json={"status": "in_storage", "location": "Depot"}, headers=admin_headers)

    p = (await client.get(f"/api/v1/assets/{asset_id}/passport", headers=admin_headers)).json()
    assert p["current_status"] == "in_storage"
    assert p["current_location"] == "Depot"
    assert p["repair_count"] == 1

    types = [e["event_type"] for e in p["events"]]  # newest first
    assert "created" in types
    assert types.count("status_changed") == 2
    assert "location_changed" in types
    # Time has been attributed across statuses (in_use + in_repair + in_storage seen).
    statuses_tracked = {d["status"] for d in p["time_in_status"]}
    assert {"in_use", "in_repair", "in_storage"} <= statuses_tracked


async def test_passport_tracks_assignment_history(client, admin_headers, regular_user, session_factory):
    created = await _create(client, admin_headers)
    asset_id = created.json()["id"]

    # Assign -> unassign -> reassign.
    await client.patch(f"/api/v1/assets/{asset_id}",
                       json={"assigned_to_user_id": str(regular_user.id)}, headers=admin_headers)
    await client.patch(f"/api/v1/assets/{asset_id}",
                       json={"assigned_to_user_id": None}, headers=admin_headers)
    await client.patch(f"/api/v1/assets/{asset_id}",
                       json={"assigned_to_user_id": str(regular_user.id)}, headers=admin_headers)

    p = (await client.get(f"/api/v1/assets/{asset_id}/passport", headers=admin_headers)).json()
    assert p["assignment_count"] == 2
    assert p["current_holder"] == regular_user.full_name
    assert p["holder_since"] is not None
    types = [e["event_type"] for e in p["events"]]
    assert types.count("assigned") == 2
    assert types.count("unassigned") == 1


async def test_passport_records_acknowledgement(client, admin_headers, regular_user, session_factory):
    created = await _create(client, admin_headers, assigned_to_user_id=str(regular_user.id))
    asset_id = created.json()["id"]
    async with session_factory() as s:
        token = (await s.execute(select(Asset).where(Asset.id == uuid.UUID(asset_id)))).scalar_one().ack_token

    await client.get(f"/api/v1/assets/acknowledge?token={token}")

    p = (await client.get(f"/api/v1/assets/{asset_id}/passport", headers=admin_headers)).json()
    assert any(e["event_type"] == "acknowledged" for e in p["events"])
    # Created-with-assignee logs a 'created' and an 'assigned'.
    assert any(e["event_type"] == "assigned" for e in p["events"])


async def test_passport_requires_ownership(client, admin_headers, session_factory):
    # An asset id from another org (random) → 404.
    missing = await client.get(f"/api/v1/assets/{uuid.uuid4()}/passport", headers=admin_headers)
    assert missing.status_code == 404
