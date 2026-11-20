async def _create(client, headers, **overrides):
    payload = {"name": "Dell Latitude 5540", "category": "laptop", "status": "in_use"}
    payload.update(overrides)
    return await client.post("/api/v1/assets", json=payload, headers=headers)


async def test_create_and_list_asset(client, admin_headers):
    created = await _create(
        client, admin_headers, asset_tag="AST-001", manufacturer="Dell",
        serial_number="SN123", purchase_cost=1200.0, warranty_expiry="2027-01-01",
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name"] == "Dell Latitude 5540"
    assert body["category"] == "laptop"
    assert body["asset_tag"] == "AST-001"

    listed = await client.get("/api/v1/assets", headers=admin_headers)
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1
    assert listed.json()["items"][0]["serial_number"] == "SN123"


async def test_asset_summary(client, admin_headers):
    await _create(client, admin_headers, category="laptop", status="in_use", purchase_cost=1000.0)
    await _create(client, admin_headers, category="monitor", status="in_storage", purchase_cost=200.0)
    await _create(client, admin_headers, category="laptop", status="retired")

    resp = await client.get("/api/v1/assets/summary", headers=admin_headers)
    assert resp.status_code == 200
    s = resp.json()
    assert s["total"] == 3
    assert s["by_category"]["laptop"] == 2
    assert s["by_status"]["in_storage"] == 1
    assert s["total_value"] == 1200.0


async def test_update_asset(client, admin_headers):
    created = await _create(client, admin_headers)
    asset_id = created.json()["id"]
    resp = await client.patch(
        f"/api/v1/assets/{asset_id}",
        json={"status": "in_repair", "location": "Head Office"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_repair"
    assert resp.json()["location"] == "Head Office"


async def test_delete_asset(client, admin_headers):
    created = await _create(client, admin_headers)
    asset_id = created.json()["id"]
    resp = await client.delete(f"/api/v1/assets/{asset_id}", headers=admin_headers)
    assert resp.status_code == 204
    listed = await client.get("/api/v1/assets", headers=admin_headers)
    assert listed.json()["items"] == []


async def test_assigned_user_name_is_enriched(client, admin_headers, admin_user):
    created = await _create(
        client, admin_headers, assigned_to_user_id=str(admin_user.id)
    )
    assert created.status_code == 201
    assert created.json()["assigned_to_name"] == admin_user.full_name


async def test_regular_user_can_read_but_not_write(client, admin_headers, user_headers):
    await _create(client, admin_headers)
    # read allowed
    listed = await client.get("/api/v1/assets", headers=user_headers)
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1
    # write forbidden
    forbidden = await _create(client, user_headers, name="Sneaky asset")
    assert forbidden.status_code == 403


async def test_assets_require_auth(client):
    assert (await client.get("/api/v1/assets")).status_code == 401


async def test_assets_are_org_scoped(client, admin_headers, other_org_user):
    created = await _create(client, admin_headers)
    asset_id = created.json()["id"]

    other = await client.post(
        "/api/v1/auth/login",
        json={"email": other_org_user.email, "password": "UserPassw0rd!2345"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}

    # other org sees none, and cannot fetch the asset by id
    assert (await client.get("/api/v1/assets", headers=other_headers)).json()["items"] == []
    assert (await client.get(f"/api/v1/assets/{asset_id}", headers=other_headers)).status_code == 404


async def test_create_records_audit_log(client, admin_headers):
    await _create(client, admin_headers)
    logs = await client.get("/api/v1/audit-logs", headers=admin_headers)
    assert logs.status_code == 200
    actions = [entry["action"] for entry in logs.json()["items"]]
    assert "asset.create" in actions


async def _other_org_device(session_factory, other_org):
    from app.models import Device

    async with session_factory() as session:
        device = Device(
            org_id=other_org.id, hostname="GLOBEX-PC", machine_id="globex-pc",
            os_version="Windows 11", agent_version="0.1.0", token_hash="globex-device-token",
        )
        session.add(device)
        await session.commit()
        return device


async def test_create_refuses_other_orgs_user(client, admin_headers, other_org_user):
    resp = await _create(client, admin_headers, assigned_to_user_id=str(other_org_user.id))
    assert resp.status_code == 404
    listed = await client.get("/api/v1/assets", headers=admin_headers)
    assert listed.json()["items"] == []


async def test_create_refuses_other_orgs_device(client, admin_headers, session_factory, other_org):
    device = await _other_org_device(session_factory, other_org)
    resp = await _create(client, admin_headers, device_id=str(device.id))
    assert resp.status_code == 404
    listed = await client.get("/api/v1/assets", headers=admin_headers)
    assert listed.json()["items"] == []


async def test_update_refuses_other_orgs_user(client, admin_headers, other_org_user):
    asset_id = (await _create(client, admin_headers)).json()["id"]
    resp = await client.patch(
        f"/api/v1/assets/{asset_id}",
        json={"assigned_to_user_id": str(other_org_user.id)},
        headers=admin_headers,
    )
    assert resp.status_code == 404
    after = (await client.get(f"/api/v1/assets/{asset_id}", headers=admin_headers)).json()
    assert after["assigned_to_user_id"] is None
    assert after["assigned_to_name"] is None


async def test_update_refuses_other_orgs_device(client, admin_headers, session_factory, other_org):
    device = await _other_org_device(session_factory, other_org)
    asset_id = (await _create(client, admin_headers)).json()["id"]
    resp = await client.patch(
        f"/api/v1/assets/{asset_id}", json={"device_id": str(device.id)}, headers=admin_headers
    )
    assert resp.status_code == 404
    after = (await client.get(f"/api/v1/assets/{asset_id}", headers=admin_headers)).json()
    assert after["device_id"] is None


async def test_update_can_still_clear_links(client, admin_headers, admin_user):
    asset_id = (await _create(client, admin_headers, assigned_to_user_id=str(admin_user.id))).json()["id"]
    resp = await client.patch(
        f"/api/v1/assets/{asset_id}",
        json={"assigned_to_user_id": None, "device_id": None},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["assigned_to_user_id"] is None
