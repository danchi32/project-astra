from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.database import get_db
from app.models import User, UserRole
from app.repositories.audit_logs import AuditLogRepository
from app.repositories.users import UserRepository
from app.schemas.audit import AuditLogRead
from app.schemas.pagination import DEFAULT_PAGE_SIZE, Page, build, clamp

router = APIRouter(prefix="/audit-logs", tags=["audit"])

staff_required = require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)


@router.get("", response_model=Page[AuditLogRead], summary="List audit log entries")
async def list_audit_logs(
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> Page[AuditLogRead]:
    page, page_size = clamp(page, page_size)
    entries, total = await AuditLogRepository(session).list_page(
        actor.org_id, offset=(page - 1) * page_size, limit=page_size
    )
    # Actor emails are resolved for the page only. This used to load every user in the org
    # to label at most `limit` rows.
    actor_ids = {e.actor_id for e in entries if e.actor_id}
    email_by_id = await UserRepository(session).emails_for(actor.org_id, actor_ids)
    items: list[AuditLogRead] = []
    for entry in entries:
        read = AuditLogRead.model_validate(entry)
        read.actor_email = email_by_id.get(entry.actor_id) if entry.actor_id else None
        items.append(read)
    return build(items, total, page, page_size)
