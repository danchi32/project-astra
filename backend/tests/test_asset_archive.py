"""Archive (soft-delete): keeps the asset + passport, removes it from the active register,
restorable; permanent delete is admin-only."""


async def _create(client, headers, **overrides):
    payload = {"name": "Old Laptop", "category": "laptop", "status": "in_use"}
    payload.update(overrides)
    return await client.post("/api/v1/assets", json=payload, headers=headers)


async def test_archive_hides_from_active_but_kept_in_archived(client, admin_headers):
    a = await _create(client, admin_headers)
    aid = a.json()["id"]

    r = await client.post(f"/api/v1/assets/{aid}/archive", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["archived_at"] is not None

    active = (await client.get("/api/v1/assets", headers=admin_headers)).json()
    assert all(x["id"] != aid for x in active)

    archived = (await client.get("/api/v1/assets?archived=true", headers=admin_headers)).json()
    assert any(x["id"] == aid for x in archived)


async def test_passport_survives_archive(client, admin_headers):
    a = await _create(client, admin_headers)
    aid = a.json()["id"]
    await client.post(f"/api/v1/assets/{aid}/archive", headers=admin_headers)

    p = await client.get(f"/api/v1/assets/{aid}/passport", headers=admin_headers)
    assert p.status_code == 200, p.text
    assert any(e["event_type"] == "archived" for e in p.json()["events"])


async def test_restore_returns_to_active(client, admin_headers):
    a = await _create(client, admin_headers)
    aid = a.json()["id"]
    await client.post(f"/api/v1/assets/{aid}/archive", headers=admin_headers)

    r = await client.post(f"/api/v1/assets/{aid}/restore", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["archived_at"] is None
    active = (await client.get("/api/v1/assets", headers=admin_headers)).json()
    assert any(x["id"] == aid for x in active)
    # ...and a 'restored' event is on the passport.
    p = (await client.get(f"/api/v1/assets/{aid}/passport", headers=admin_headers)).json()
    assert any(e["event_type"] == "restored" for e in p["events"])


async def test_archived_excluded_from_summary(client, admin_headers):
    a = await _create(client, admin_headers, status="in_use")
    aid = a.json()["id"]
    before = (await client.get("/api/v1/assets/summary", headers=admin_headers)).json()
    await client.post(f"/api/v1/assets/{aid}/archive", headers=admin_headers)
    after = (await client.get("/api/v1/assets/summary", headers=admin_headers)).json()
    assert after["total"] == before["total"] - 1


async def test_permanent_delete_is_admin_only(client, admin_headers, user_headers):
    a = await _create(client, admin_headers)
    aid = a.json()["id"]
    # A non-admin cannot permanently delete.
    assert (await client.delete(f"/api/v1/assets/{aid}", headers=user_headers)).status_code == 403
    # An admin can.
    assert (await client.delete(f"/api/v1/assets/{aid}", headers=admin_headers)).status_code == 204
