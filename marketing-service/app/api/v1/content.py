"""Content endpoints.

Every one of these needs the admin token. Nothing here is public: the drafts are unpublished
marketing copy, the events name who approved what, and `publish` is the door.

`POST /{id}/published` is the narrowest endpoint in the service and the most important. It
does not publish — the publisher calls the platform and then calls this to record it — but
it refuses to record a publication the gate would not have allowed, so a caller that
skipped the gate cannot launder the result through it.
"""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.content import ContentItem, ContentStatus
from app.schemas.content import (
    ApproveRequest,
    ContentDetail,
    ContentRead,
    DraftRequest,
    PublishedRequest,
    ReviseRequest,
    ScheduleRequest,
    SimpleActorRequest,
)
from app.services.approval_desk import ApprovalDesk
from app.services.cards import CardError, fallback_line
from app.services.cards import render as render_card
from app.services.content import ContentService, PublishRefused
from app.services.drafting import DraftingAgent
from app.services.exceptions import NotConfiguredError, NotFoundError, ValidationError
from app.services.publishers.base import PublisherError
from app.services.publishing import PublishedButNotRecorded, PublishingService

logger = logging.getLogger("astra.mkt.api.content")
router = APIRouter(prefix="/content", tags=["content"], dependencies=[Depends(require_admin)])


def _not_found(exc: NotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def _invalid(exc: ValidationError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("/draft", response_model=ContentDetail, status_code=status.HTTP_201_CREATED,
             summary="Write a new piece from a brief")
async def draft(body: DraftRequest, session: AsyncSession = Depends(get_db)) -> ContentDetail:
    """Draft, check, and store as version 1.

    A draft the checker refuses is still stored. It cannot be submitted for review, but
    discarding it would hide the one thing worth knowing — that this brief, through this
    prompt, produces a claim the product cannot support.
    """
    agent = DraftingAgent()
    try:
        result = await agent.draft(
            channel=body.channel, brief=body.brief, campaign=body.campaign
        )
    except NotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    service = ContentService(session)
    item = await service.create(
        channel=body.channel, brief=body.brief, campaign=body.campaign,
        body=result.draft.body, headline=result.draft.headline,
        hashtags=result.draft.hashtags, cta=result.draft.cta,
        card_line=result.draft.card_line,
        actor="drafting-agent", authored_by=agent_label(result),
    )
    if result.blocked:
        logger.warning(
            "stored a blocked draft %s after %d attempts: %s",
            item.id, result.attempts, [f.rule for f in result.findings if f.severity == "blocker"],
        )
    return ContentDetail.model_validate(await service.get(item.id))


def agent_label(result) -> str:
    from app.core.config import get_settings

    return f"{get_settings().drafting_model} (attempt {result.attempts})"


@router.post("/{item_id}/revise", response_model=ContentDetail,
             summary="Rewrite in response to feedback")
async def revise(
    item_id: uuid.UUID, body: ReviseRequest, session: AsyncSession = Depends(get_db)
) -> ContentDetail:
    service = ContentService(session)
    try:
        item = await service.get(item_id)
        current = await service.current_version(item)
        if current is None:
            raise ValidationError("Nothing to revise.")

        agent = DraftingAgent()
        result = await agent.revise(
            channel=item.channel, previous=current.body,
            feedback=body.feedback, brief=item.brief,
        )
        await service.revise(
            item_id, body=result.draft.body, headline=result.draft.headline,
            hashtags=result.draft.hashtags, cta=result.draft.cta,
            card_line=result.draft.card_line,
            actor=body.actor, reason=body.feedback, authored_by=agent_label(result),
        )
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    except ValidationError as exc:
        raise _invalid(exc) from exc
    except NotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return ContentDetail.model_validate(await service.get(item_id))


@router.post("/{item_id}/submit", response_model=ContentDetail,
             summary="Send it to a human")
async def submit(
    item_id: uuid.UUID, body: SimpleActorRequest, session: AsyncSession = Depends(get_db)
) -> ContentDetail:
    """Run the blocking claim check, then put it on the Telegram desk.

    Posting is part of submitting, not a second call someone has to remember. "Submitted
    for review" that sits in a table nobody opens is how a queue silently becomes a
    graveyard — and the reviewer here reviews on a phone, not in a portal.

    The post is best-effort and comes *after* the transition. Telegram being unreachable
    must not undo a submission that already passed the claim check; the item stays
    IN_REVIEW and can be re-posted by submitting again.
    """
    service = ContentService(session)
    try:
        await service.submit_for_review(item_id, actor=body.actor)
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    except ValidationError as exc:
        raise _invalid(exc) from exc

    item = await service.get(item_id)
    desk = ApprovalDesk(session)
    if desk.enabled:
        try:
            await desk.post_for_review(item)
        except Exception:  # noqa: BLE001 — a failed notification must not fail the submit
            logger.exception("submitted %s but could not post it to the desk", item_id)
    return ContentDetail.model_validate(await service.get(item_id))


@router.post("/{item_id}/approve", response_model=ContentDetail,
             summary="Approve one named version")
async def approve(
    item_id: uuid.UUID, body: ApproveRequest, session: AsyncSession = Depends(get_db)
) -> ContentDetail:
    service = ContentService(session)
    try:
        await service.approve(item_id, actor=body.actor, version_id=body.version_id)
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    except ValidationError as exc:
        raise _invalid(exc) from exc
    return ContentDetail.model_validate(await service.get(item_id))


@router.post("/{item_id}/request-changes", response_model=ContentDetail,
             summary="Ask for something different")
async def request_changes(
    item_id: uuid.UUID, body: ReviseRequest, session: AsyncSession = Depends(get_db)
) -> ContentDetail:
    service = ContentService(session)
    try:
        await service.request_changes(item_id, actor=body.actor, feedback=body.feedback)
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    except ValidationError as exc:
        raise _invalid(exc) from exc
    return ContentDetail.model_validate(await service.get(item_id))


@router.post("/{item_id}/schedule", response_model=ContentDetail,
             summary="Queue an approved piece for a time")
async def schedule(
    item_id: uuid.UUID, body: ScheduleRequest, session: AsyncSession = Depends(get_db)
) -> ContentDetail:
    service = ContentService(session)
    try:
        await service.schedule(item_id, actor=body.actor, when=body.when)
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    except ValidationError as exc:
        raise _invalid(exc) from exc
    except PublishRefused as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ContentDetail.model_validate(await service.get(item_id))


@router.post("/{item_id}/published", response_model=ContentDetail,
             summary="Record that the approved version went out")
async def mark_published(
    item_id: uuid.UUID, body: PublishedRequest, session: AsyncSession = Depends(get_db)
) -> ContentDetail:
    """The gate. A refusal here is a 409 and an event, never a silent no-op."""
    service = ContentService(session)
    try:
        await service.mark_published(item_id, actor=body.actor, url=body.url, ref=body.ref)
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    except PublishRefused as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ContentDetail.model_validate(await service.get(item_id))


@router.get("/{item_id}/card.png", summary="The image that goes out with this post",
            response_class=Response)
async def card(item_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> Response:
    """Render the card on demand.

    Not stored anywhere. Rendering is a pure function of an approved version, so the image
    can be regenerated byte-identically whenever it is wanted — which is cheaper and less
    fragile than a bucket, and removes any chance of the stored image and the approved
    words drifting apart.
    """
    service = ContentService(session)
    try:
        item = await service.get(item_id)
        version = await service.current_version(item)
        if version is None:
            raise ValidationError("Nothing to draw.")

        line = version.card_line or fallback_line(version.body)
        png = render_card(line, eyebrow=item.campaign or item.channel.value)
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    except (ValidationError, CardError) as exc:
        raise _invalid(exc) from exc

    return Response(
        content=png, media_type="image/png",
        # Cached for a minute only: a revision changes the card, and a stale graphic is
        # the sort of thing that gets posted by mistake.
        headers={"Cache-Control": "private, max-age=60",
                 "Content-Disposition": f'inline; filename="astra-{item_id}.png"'},
    )


@router.get("/{item_id}/preview", summary="Exactly what would be posted, without posting")
async def preview(item_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> dict:
    """A dry run.

    The platform's escaping and hashtag templating make the wire format differ visibly
    from the approved text, and for an action nobody can undo that difference should be
    inspectable beforehand rather than discovered on the page.
    """
    try:
        return await PublishingService(session).preview(item_id)
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    except ValidationError as exc:
        raise _invalid(exc) from exc
    except PublishRefused as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{item_id}/publish", summary="Post the approved version for real")
async def publish(
    item_id: uuid.UUID, body: SimpleActorRequest, session: AsyncSession = Depends(get_db)
) -> dict:
    """The irreversible one.

    Distinct from `/published`, which only records something a caller already posted
    elsewhere. This one goes through the gate and then out to the platform.
    """
    service = PublishingService(session)
    try:
        result = await service.publish(item_id, actor=body.actor)
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    except (PublishRefused, ValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except PublishedButNotRecorded as exc:
        # 500, deliberately. The request did not do what was asked, a human has to
        # reconcile, and the detail carries the live URL so they can start.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc
    except PublisherError as exc:
        # 502: the failure is on the far side, not in the request. `retryable` tells a
        # caller whether trying again could plausibly help.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc), headers={"X-Retryable": str(exc.retryable).lower()},
        ) from exc
    return {"ref": result.ref, "url": result.url, "characters": len(result.rendered or "")}


@router.post("/publish-due", summary="Publish everything scheduled and due")
async def publish_due(
    body: SimpleActorRequest, session: AsyncSession = Depends(get_db)
) -> dict:
    """For the scheduler.

    Being due is not permission — each item still goes through the gate individually, and
    one refusal does not stop the queue. The response says what happened to every item,
    including the ones that did not go out and why.
    """
    return await PublishingService(session).publish_due(actor=body.actor)


@router.get("", response_model=list[ContentRead], summary="List content")
async def list_content(
    status_filter: ContentStatus | None = None, limit: int = 50,
    session: AsyncSession = Depends(get_db),
) -> list[ContentRead]:
    from sqlalchemy import select

    stmt = select(ContentItem).order_by(ContentItem.created_at.desc()).limit(min(limit, 200))
    if status_filter is not None:
        stmt = stmt.where(ContentItem.status == status_filter)
    rows = (await session.execute(stmt)).scalars().all()
    return [ContentRead.model_validate(r) for r in rows]


@router.get("/{item_id}", response_model=ContentDetail, summary="One piece with its history")
async def get_content(
    item_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> ContentDetail:
    try:
        return ContentDetail.model_validate(await ContentService(session).get(item_id))
    except NotFoundError as exc:
        raise _not_found(exc) from exc
