"""Lead intake and read endpoints.

`POST /leads/intake` is the only endpoint on this service reachable from outside our own
infrastructure, so it carries all of the paranoia: HMAC signature over the raw body, a
freshness window, a body-size ceiling, and a refusal to operate at all when unconfigured.
"""
import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import SignatureError, verify
from app.repositories.leads import LeadRepository
from app.schemas.lead import LeadDetail, LeadIntake, LeadIntakeAccepted, LeadRead
from app.services.bigin import BiginError
from app.services.exceptions import NotConfiguredError, NotFoundError
from app.services.leads import LeadService

logger = logging.getLogger("astra.mkt.api.leads")
router = APIRouter(prefix="/leads", tags=["leads"])
settings = get_settings()

#: A contact form message is capped at 5,000 characters by the website. 64 KB leaves room
#: for the attribution fields and generous headroom, while making it pointless to try to
#: exhaust memory here.
_MAX_BODY_BYTES = 64 * 1024


@router.post(
    "/intake",
    response_model=LeadIntakeAccepted,
    status_code=status.HTTP_201_CREATED,
    summary="Record a lead from the marketing website",
)
async def intake(
    request: Request,
    session: AsyncSession = Depends(get_db),
    x_astra_timestamp: str | None = Header(default=None),
    x_astra_signature: str | None = Header(default=None),
) -> LeadIntakeAccepted:
    """Store a form submission, then hand it to the automation.

    The response is returned after the commit but regardless of whether the dispatch
    succeeded — the visitor's form should not fail because n8n is restarting.
    """
    body = await request.body()
    if len(body) > _MAX_BODY_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Payload too large.",
        )

    try:
        verify(
            secret=settings.intake_secret,
            timestamp=x_astra_timestamp,
            signature=x_astra_signature,
            body=body,
            max_skew_seconds=settings.intake_max_skew_seconds,
        )
    except SignatureError as exc:
        if not settings.intake_secret:
            # Configuration, not attack. Say so plainly in the logs so this does not get
            # mistaken for someone probing the endpoint.
            logger.error("lead intake called but ASTRA_MKT_INTAKE_SECRET is not set")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Lead intake is not configured.",
            ) from exc
        # Never echo the reason back. A caller who cannot sign has no business learning
        # whether it was the timestamp or the digest that let them down.
        logger.warning("rejected unsigned/invalid lead intake: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature."
        ) from exc

    try:
        payload = LeadIntake.model_validate_json(body)
    except PydanticValidationError as exc:
        # The signature was valid, so this is our own website sending something we did not
        # expect — a real bug worth the log line, not a hostile request.
        logger.warning("signed lead intake failed validation: %s", exc.errors()[:3])
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Please provide a valid email address.",
        ) from exc

    service = LeadService(session)
    captured = await service.capture(payload)

    # Everything past this point is best-effort and runs concurrently. The lead is
    # committed; the visitor is owed a response, not a fully fanned-out pipeline.
    await service.fan_out(captured.lead, captured.submission)

    return LeadIntakeAccepted(
        lead_id=captured.lead.id,
        submission_id=captured.submission.id,
        is_new_lead=captured.is_new_lead,
    )


@router.post(
    "/{lead_id}/rescore",
    response_model=LeadRead,
    summary="Re-run scoring, including the model pass",
    dependencies=[Depends(require_admin)],
)
async def rescore_lead(
    lead_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> LeadRead:
    """Called by the automation shortly after capture.

    Separate from intake because the model call costs about a second and the visitor's
    form must not wait for it. Idempotent — running it twice on an unchanged lead gives
    the same answer, so a retry is harmless.
    """
    try:
        lead = await LeadService(session).rescore(lead_id)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found."
        ) from exc
    return LeadRead.model_validate(lead)


@router.post(
    "/sync-pending",
    summary="Sync every lead that has never reached the CRM",
    dependencies=[Depends(require_admin)],
)
async def sync_pending(
    limit: int = 25, session: AsyncSession = Depends(get_db)
) -> dict[str, int]:
    """The safety net behind the automation, and the manual button until it exists.

    Declared before `/{lead_id}/...` would otherwise be a routing hazard — FastAPI matches
    in definition order, and a literal path registered after a parameterised one is
    unreachable. It is above the GET routes for the same reason.
    """
    return await LeadService(session).sync_pending(limit=min(limit, 100))


@router.post(
    "/{lead_id}/sync-crm",
    response_model=LeadRead,
    summary="Push one lead to Bigin",
    dependencies=[Depends(require_admin)],
)
async def sync_lead_to_crm(
    lead_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> LeadRead:
    try:
        lead = await LeadService(session).sync_to_crm(lead_id)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found."
        ) from exc
    except NotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except BiginError as exc:
        # Bigin's own message is usually specific ("INVALID_DATA: Stage"), and losing it
        # turns a five-second fix into an afternoon.
        logger.warning("bigin rejected lead %s: %s", lead_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Bigin refused: {exc}"
        ) from exc
    return LeadRead.model_validate(lead)


@router.get(
    "",
    response_model=list[LeadRead],
    summary="List recent leads",
    dependencies=[Depends(require_admin)],
)
async def list_leads(
    limit: int = 50, offset: int = 0, session: AsyncSession = Depends(get_db)
) -> list[LeadRead]:
    leads = await LeadRepository(session).list_recent(limit=min(limit, 200), offset=offset)
    return [LeadRead.model_validate(lead) for lead in leads]


@router.get(
    "/{lead_id}",
    response_model=LeadDetail,
    summary="One lead with its submissions",
    dependencies=[Depends(require_admin)],
)
async def get_lead(lead_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> LeadDetail:
    lead = await LeadRepository(session).get_with_submissions(lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found.")
    return LeadDetail.model_validate(lead)
