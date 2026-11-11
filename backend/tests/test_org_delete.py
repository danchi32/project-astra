"""G3 — deleting an organisation deletes ALL of its data, not only what cascades."""
from sqlalchemy import func, select

from app.models import (
    Asset,
    AssetEvent,
    AssetEventType,
    Assistant,
    AssistantVersion,
    AssistantVersionStatus,
    AuditLog,
    Base,
    Deployment,
    KnowledgeArticle,
    KnowledgeSource,
    LearnedAction,
    Notification,
    SemanticCacheEntry,
    User,
)
from app.models.base import utcnow
from app.services.platform import ORG_ROWS_WITHOUT_CASCADE


def _cascades_to_org(table, seen=()) -> bool:
    for fk in table.foreign_keys:
        if fk.ondelete != "CASCADE":
            continue
        target = fk.column.table
        if target.name == "organizations" or (
                target.name not in seen and _cascades_to_org(target, (*seen, table.name))):
            return True
    return False


def test_every_org_table_is_covered():
    # A new table with org_id must either cascade from organizations or be deleted by hand,
    # or it silently outlives every deleted customer.
    listed = {m.__tablename__ for m in ORG_ROWS_WITHOUT_CASCADE}
    missing = [t.name for t in Base.metadata.sorted_tables
               if "org_id" in t.c and t.name not in listed and not _cascades_to_org(t)]
    assert missing == []


async def _seed(s, org_id):
    now = utcnow()
    asset = Asset(org_id=org_id, name="Laptop")
    assistant = Assistant(org_id=org_id, name="Helper")
    s.add_all([asset, assistant])
    await s.flush()
    s.add_all([
        AssetEvent(org_id=org_id, asset_id=asset.id, event_type=AssetEventType.ASSIGNED, to_value="Asha",
                   occurred_at=now),
        AssistantVersion(assistant_id=assistant.id, version_no=1, status=AssistantVersionStatus.DRAFT),
        Deployment(org_id=org_id, action_id="install_package", title="7-Zip", reason="r"),
        Notification(org_id=org_id, title="t", message="m"),
        SemanticCacheEntry(org_id=org_id, query_text="why is asha's vpn slow", embedding=[0.0],
                           embedding_model="hash", answer="a"),
        KnowledgeArticle(org_id=org_id, title="t", content="c", embedding=[0.0], embedding_model="hash",
                         source=KnowledgeSource.MANUAL),
        LearnedAction(org_id=org_id, query_text="q", embedding=[0.0], embedding_model="hash",
                      action_id="flush_dns"),
        AuditLog(org_id=org_id, action="user.update", target_type="user", detail={"email": "asha@x.com"}),
    ])


async def test_delete_org_leaves_nothing_behind(client, admin_user, admin_headers, other_org, session_factory):
    async with session_factory() as s:
        (await s.get(User, admin_user.id)).is_platform_admin = True
        await _seed(s, other_org.id)
        await _seed(s, admin_user.org_id)          # the org that must survive
        await s.commit()

    r = await client.delete(f"/api/v1/platform/organizations/{other_org.id}", headers=admin_headers)
    assert r.status_code == 204, r.text

    async with session_factory() as s:
        for model in ORG_ROWS_WITHOUT_CASCADE:
            gone = await s.scalar(select(func.count()).select_from(model).where(model.org_id == other_org.id))
            kept = await s.scalar(select(func.count()).select_from(model).where(model.org_id == admin_user.org_id))
            if model is AuditLog:
                # Only the deletion record remains: the org's name and who deleted it.
                rows = (await s.execute(select(AuditLog).where(AuditLog.org_id == other_org.id))).scalars().all()
                assert [a.action for a in rows] == ["platform.organization.delete"]
            else:
                assert gone == 0, model.__tablename__
            assert kept >= 1, model.__tablename__
        assert await s.scalar(select(func.count()).select_from(AssistantVersion)) == 1
