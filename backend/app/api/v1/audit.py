from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.database import get_db
from app.models import User, UserRole
from app.repositories.audit_logs import AuditLogRepository
from app.repositories.users import UserRepository
from app.schemas.audit import AuditLogRead

router = APIRouter(prefix="/audit-logs", tags=["audit"])

staff_required = require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)


@router.get("", response_model=list[AuditLogRead], summary="List audit log entries")
async def list_audit_logs(
    limit: int = Query(default=200, ge=1, le=1000),
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> list[AuditLogRead]:
    entries = await AuditLogRepository(session).list_by_org(actor.org_id, limit=limit)
    users = await UserRepository(session).list_by_org(actor.org_id)
    email_by_id = {u.id: u.email for u in users}
    result: list[AuditLogRead] = []
    for entry in entries:
        read = AuditLogRead.model_validate(entry)
        read.actor_email = email_by_id.get(entry.actor_id) if entry.actor_id else None
        result.append(read)
    return result
