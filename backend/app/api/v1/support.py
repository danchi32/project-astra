"""An organization asking ASTRA for help.

Open to every authenticated role. The person who cannot get the agent installed is often
not an administrator, and a support channel they cannot reach is not a support channel —
though what each role can *see* differs, which the service enforces.
"""
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import SupportRequestStatus, User
from app.schemas.support_request import (
    SupportMessageRead,
    SupportReplyCreate,
    SupportRequestCreate,
    SupportRequestRead,
    SupportRequestSummary,
)
from app.services.support_requests import SupportRequestService

router = APIRouter(prefix="/support", tags=["support"])


async def thread_detail(
    service: SupportRequestService, *, actor: User, request_id: uuid.UUID, operator: bool = False
) -> SupportRequestRead:
    """Assemble one thread. Shared with the operator routes, which differ only in who is
    allowed to open it."""
    request = await service.get(actor=actor, request_id=request_id, operator=operator)
    messages = await service.messages(actor=actor, request_id=request_id, operator=operator)
    emails = await service.author_emails(messages)
    read = SupportRequestRead.model_validate(request)
    if operator:
        # An operator reads threads from every customer, so the thread has to say which
        # one it belongs to. Inside an organization the answer is "yours" and naming it
        # would be noise.
        read.org_name = await service.org_name(request.org_id)
    read.messages = [
        SupportMessageRead(
            id=m.id, body=m.body, from_operator=m.from_operator,
            author_email=emails.get(m.author_user_id), created_at=m.created_at,
        )
        for m in messages
    ]
    return read


@router.get(
    "/requests",
    response_model=list[SupportRequestSummary],
    summary="List this organization's support requests",
)
async def list_requests(
    request_status: SupportRequestStatus | None = None,
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[SupportRequestSummary]:
    """Staff see the whole organization's requests; everyone else sees their own."""
    rows = await SupportRequestService(session).list_for_org(actor=actor, status=request_status)
    return [SupportRequestSummary.model_validate(r) for r in rows]


@router.post(
    "/requests",
    response_model=SupportRequestRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ask ASTRA for help",
)
async def create_request(
    body: SupportRequestCreate,
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SupportRequestRead:
    """A snapshot of the organization's fleet is captured server-side and attached, so the
    request arrives explained. It is returned here too — the customer sees exactly what
    was sent."""
    service = SupportRequestService(session)
    request = await service.create(
        actor=actor, subject=body.subject, body=body.body,
        category=body.category, priority=body.priority,
    )
    return await thread_detail(service, actor=actor, request_id=request.id)


@router.get(
    "/requests/{request_id}",
    response_model=SupportRequestRead,
    summary="Read one support thread",
)
async def get_request(
    request_id: uuid.UUID,
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SupportRequestRead:
    return await thread_detail(SupportRequestService(session), actor=actor, request_id=request_id)


@router.post(
    "/requests/{request_id}/replies",
    response_model=SupportRequestRead,
    status_code=status.HTTP_201_CREATED,
    summary="Reply on a support thread",
)
async def reply_to_request(
    request_id: uuid.UUID,
    body: SupportReplyCreate,
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SupportRequestRead:
    service = SupportRequestService(session)
    await service.reply(actor=actor, request_id=request_id, body=body.body, from_operator=False)
    return await thread_detail(service, actor=actor, request_id=request_id)
