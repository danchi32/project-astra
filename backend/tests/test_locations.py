"""Managed locations: CRUD, rename-cascade to assets, and delete-while-in-use guard."""


async def _asset(client, headers, name, location=None):
    body = {"name": name, "category": "laptop"}
    if location is not None:
        body["location"] = location
    return await client.post("/api/v1/assets", json=body, headers=headers)


async def test_create_list_and_count(client, admin_headers):
    created = await client.post("/api/v1/locations", json={"name": "HQ"}, headers=admin_headers)
    assert created.status_code == 201, created.text
    assert created.json()["name"] == "HQ"
    assert created.json()["asset_count"] == 0

    # An asset in that location bumps its count.
    await _asset(client, admin_headers, "Laptop 1", location="HQ")
    listing = (await client.get("/api/v1/locations", headers=admin_headers)).json()
    hq = next(l for l in listing if l["name"] == "HQ")
    assert hq["asset_count"] == 1


async def test_duplicate_name_rejected(client, admin_headers):
    await client.post("/api/v1/locations", json={"name": "Warehouse"}, headers=admin_headers)
    dup = await client.post("/api/v1/locations", json={"name": "warehouse"}, headers=admin_headers)
    assert dup.status_code == 409


async def test_rename_cascades_to_assets(client, admin_headers):
    loc = (await client.post("/api/v1/locations", json={"name": "SF"}, headers=admin_headers)).json()
    a = await _asset(client, admin_headers, "Mac", location="SF")
    asset_id = a.json()["id"]

    renamed = await client.patch(
        f"/api/v1/locations/{loc['id']}", json={"name": "San Francisco"}, headers=admin_headers
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["asset_count"] == 1

    # The asset now carries the new location name.
    got = (await client.get(f"/api/v1/assets/{asset_id}", headers=admin_headers)).json()
    assert got["location"] == "San Francisco"


async def test_delete_blocked_while_in_use(client, admin_headers):
    loc = (await client.post("/api/v1/locations", json={"name": "Depot"}, headers=admin_headers)).json()
    await _asset(client, admin_headers, "Router", location="Depot")

    blocked = await client.delete(f"/api/v1/locations/{loc['id']}", headers=admin_headers)
    assert blocked.status_code == 409
    assert "reassign" in blocked.json()["detail"].lower()

    # After clearing the location, delete succeeds.
    listing = (await client.get("/api/v1/assets", headers=admin_headers)).json()
    router_asset = next(x for x in listing if x["name"] == "Router")
    await client.patch(f"/api/v1/assets/{router_asset['id']}", json={"location": ""}, headers=admin_headers)
    ok = await client.delete(f"/api/v1/locations/{loc['id']}", headers=admin_headers)
    assert ok.status_code == 204


async def test_mutations_are_admin_only(client, user_headers):
    assert (await client.post("/api/v1/locations", json={"name": "X"}, headers=user_headers)).status_code == 403
    # Reads are allowed for any member.
    assert (await client.get("/api/v1/locations", headers=user_headers)).status_code == 200
