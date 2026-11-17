"""N2 · Watchlist: what is noticed only by something NOT happening, on demand."""
from datetime import date, timedelta

from app.core.security import hash_opaque_token
from app.models import Asset, AssetCategory, Device, RemediationSource, RemediationStatus, RemediationTask
from app.models.base import utcnow
from app.models.deployment import Deployment
from app.services import watchlist


async def _device(s, org_id, host, *, seen_ago=None, created_ago=timedelta(0), version="0.15.0"):
    now = utcnow()
    d = Device(org_id=org_id, hostname=host, machine_id=host, os_version="Windows 11", agent_version=version,
               token_hash=hash_opaque_token(host), last_seen_at=now - seen_ago if seen_ago is not None else None,
               created_at=now - created_ago)
    s.add(d)
    await s.flush()
    return d


async def test_watchlist(client, admin_headers, user_headers, session_factory, admin_user, other_org, monkeypatch):
    org = admin_user.org_id
    today = date.today()
    async with session_factory() as s:
        await _device(s, org, "QUIET-10H", seen_ago=timedelta(hours=10), version="0.14.0")
        live = await _device(s, org, "LIVE", seen_ago=timedelta(minutes=1))
        await _device(s, org, "JUST-ENROLLED")                                  # never seen, new
        await _device(s, org, "NEVER-SEEN", created_ago=timedelta(days=2))
        await _device(s, other_org.id, "THEIRS", seen_ago=timedelta(days=5))
        for name, days in (("Expired", -5), ("Soon", 10), ("Mid", 45), ("Late", 80), ("Far", 120), ("Long gone", -40)):
            s.add(Asset(org_id=org, name=name, category=AssetCategory.LAPTOP,
                        warranty_expiry=(today + timedelta(days=days)).isoformat()))
        dep = Deployment(org_id=org, action_id="install_package", title="Install Google Chrome", reason="x")
        s.add(dep)
        await s.flush()
        old = utcnow() - timedelta(hours=30)

        def task(status, created, **kw):
            return RemediationTask(org_id=org, device_id=live.id, action_id="install_package", tier="approval_required",
                                   reason="x", source=RemediationSource.USER, status=status, created_at=created, **kw)

        s.add_all([
            task(RemediationStatus.APPROVED, old, deployment_id=dep.id),
            task(RemediationStatus.DISPATCHED, old),
            task(RemediationStatus.APPROVED, utcnow() - timedelta(hours=2)),     # not stuck yet
            task(RemediationStatus.SUCCEEDED, old),                               # finished
        ])
        await s.commit()

    async def latest():
        return "0.15.0"

    monkeypatch.setattr(watchlist, "latest_agent_version", latest)
    r = await client.get("/api/v1/watchlist?silent_hours=6", headers=admin_headers)
    assert r.status_code == 200, r.text
    w = r.json()

    assert [(p["hostname"], p["hours"]) for p in w["silent"]] == [("NEVER-SEEN", 48), ("QUIET-10H", 10)]
    assert [(x["name"], x["bucket"]) for x in w["warranty"]] == [
        ("Expired", "expired"), ("Soon", "30"), ("Mid", "60"), ("Late", "90")]
    assert sorted((x["state"], x["rollout"]) for x in w["stuck"]) == [
        ("never collected", "Install Google Chrome"), ("never finished", None)]
    assert w["latest_agent"] == "0.15.0" and w["agents_behind"] == [{"hostname": "QUIET-10H", "version": "0.14.0"}]

    # A longer threshold drops the 10-hour one.
    w = (await client.get("/api/v1/watchlist?silent_hours=24", headers=admin_headers)).json()
    assert [p["hostname"] for p in w["silent"]] == ["NEVER-SEEN"]
    assert (await client.get("/api/v1/watchlist", headers=user_headers)).status_code == 403


async def test_a_malformed_old_date_does_not_break_the_list(client, admin_headers, session_factory, admin_user):
    """Dates were free text before they were validated; one bad row must not 500 the page."""
    soon = (date.today() + timedelta(days=5)).isoformat()
    async with session_factory() as s:
        s.add(Asset(org_id=admin_user.org_id, name="Bad", category=AssetCategory.LAPTOP, warranty_expiry=soon[:8] + "1"))
        s.add(Asset(org_id=admin_user.org_id, name="Good", category=AssetCategory.LAPTOP, warranty_expiry=soon))
        await s.commit()
    r = await client.get("/api/v1/watchlist", headers=admin_headers)
    assert r.status_code == 200 and [w["name"] for w in r.json()["warranty"]] == ["Good"]


async def test_no_update_channel_means_no_comparison(client, admin_headers, session_factory, admin_user):
    async with session_factory() as s:
        await _device(s, admin_user.org_id, "OLD-AGENT", seen_ago=timedelta(minutes=1), version="0.10.0")
        await s.commit()
    w = (await client.get("/api/v1/watchlist", headers=admin_headers)).json()
    assert (w["latest_agent"], w["agents_behind"]) == (None, [])
