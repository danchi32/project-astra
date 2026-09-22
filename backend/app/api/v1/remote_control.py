"""Requesting, watching and ending a remote session.

Three endpoints and one rule that shapes all of them: the viewer URL is a CREDENTIAL. It
logs its bearer into the relay as the technician and puts them on a named device, so it
is minted per request, handed only to the person who asked, and never written to the
database. A column holding these would be a table of live keys to other people's screens.
"""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles, requires
from app.core.database import get_db
from app.models import (
    Device,
    Organization,
    RemoteSession,
    RemoteSessionStatus,
    User,
    UserRole,
)
from app.models.base import as_utc, utcnow
from app.schemas.pagination import Page, build, clamp
from app.schemas.remote_control import RemoteSessionRead, RemoteSessionRequest
from app.services.entitlements import REMOTE_CONTROL
from app.services.exceptions import NotFoundError
from app.services.meshcentral import MeshCentralClient
from app.services.remote_control import (
    CONSENT_TIMEOUT,
    RemoteControlError,
    RemoteControlService,
    SessionAlreadyOpenError,
)

logger = logging.getLogger(__name__)

# Gated at the router so a new endpoint in this file cannot ship ungated by somebody
# forgetting the decorator — the same discipline the compliance and fleet routers use.
router = APIRouter(
    prefix="/remote-sessions", tags=["remote control"],
    dependencies=[Depends(requires(REMOTE_CONTROL))],
)

# Requesting control of someone's screen is staff work. `UserRole.USER` is absent
# deliberately and the service refuses them again — this endpoint being reachable is
# never what authorises the act.
staff_required = require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)


async def _render(
    session: AsyncSession,
    remote_session: RemoteSession,
    *,
    actor: User | None = None,
    include_viewer_url: bool = False,
) -> RemoteSessionRead:
    out = RemoteSessionRead.model_validate(remote_session)

    device = await session.get(Device, remote_session.device_id)
    out.device_hostname = device.hostname if device else None
    requester = await session.get(User, remote_session.requested_by_user_id)
    out.requested_by_name = requester.full_name if requester else None

    if remote_session.status is RemoteSessionStatus.PENDING:
        elapsed = (utcnow() - as_utc(remote_session.requested_at)).total_seconds()
        out.expires_in_seconds = max(0, int(CONSENT_TIMEOUT.total_seconds() - elapsed))

    # The link is issued while the session is still PENDING, and that is not a hole — it
    # is how the question gets asked. Opening the viewer is what makes the prompt appear
    # on the person's screen; the relay then holds the stream until they allow it. So a
    # link hands its bearer the ability to ASK, never the ability to SEE.
    #
    # Withholding it until APPROVED was the first attempt and it deadlocked: nothing could
    # trigger the prompt, so nothing was ever approved, so no link was ever issued. The
    # consent gate lives on the relay (the device group's consent flags), where it can
    # actually stop pixels — not here, where it only stopped the question.
    #
    # Still only for the technician who asked. A colleague can read the session because it
    # is their org's record; handing them the link would hand them the session.
    if (
        include_viewer_url
        and actor is not None
        and remote_session.requested_by_user_id == actor.id
        and remote_session.status in (RemoteSessionStatus.PENDING,
                                      RemoteSessionStatus.APPROVED,
                                      RemoteSessionStatus.ACTIVE)
        and device is not None
        and device.meshcentral_node_id
    ):
        # The user the browser logs in AS is THIS org's scoped relay account, and only ever
        # that. It is the cross-tenant boundary: that account can reach this org's device
        # group and no other, so a technician who edits the node id in the URL to point at
        # someone else's machine is refused by the relay. There is no fallback to a shared
        # admin — an org with no scoped user simply gets no link, because a shared admin is
        # exactly the leak this avoids. The org lookup is by the session's own org_id, which
        # the request path already tied to the actor's org.
        org = await session.get(Organization, remote_session.org_id)
        scoped_user_id = org.meshcentral_user_id if org else None
        if scoped_user_id:
            try:
                out.viewer_url = MeshCentralClient().viewer_url(
                    node_id=device.meshcentral_node_id,
                    user_id=scoped_user_id,
                )
            except Exception:
                # The session is real and its record stands; a relay that is unset just
                # means no link to show right now. Degrade to an empty field rather than
                # failing the whole status response — the record is unaffected.
                logger.warning("could not mint a viewer URL for session %s",
                               remote_session.id, exc_info=True)
                out.viewer_url = None
    return out


async def _label_consent(
    session: AsyncSession, remote_session: RemoteSession, actor: User
) -> None:
    """Put the requester and their reason on the endpoint's own consent prompt.

    The relay draws that prompt from the connecting account's realname — the `{0}` in the
    consent template (infra/relay/apply_consent_branding.py) — so ASTRA sets the org's
    scoped account's realname to "<who> (reason: <why>)" just before the technician opens
    the viewer. The person being asked then reads who wants in and why, on their own screen,
    before anything connects.

    Best-effort: a relay that is unset or briefly unreachable just means the prompt shows
    the account's standing name, which is not worth failing the request over. The account is
    shared within the org, so two technicians requesting at the same moment can race on the
    name — acceptable at this scale, and a reason the prompt itself, not just the label, is
    what the person actually reads before allowing.
    """
    org = await session.get(Organization, remote_session.org_id)
    if not (org and org.meshcentral_user_id):
        return
    realname = f"{actor.full_name} (reason: {remote_session.reason})"
    try:
        await MeshCentralClient().set_user_realname(
            user_id=org.meshcentral_user_id, realname=realname)
    except Exception:
        logger.warning("could not label the consent prompt for session %s",
                       remote_session.id, exc_info=True)


@router.post("", response_model=RemoteSessionRead, status_code=status.HTTP_201_CREATED,
             summary="Ask the person at a device for control of their screen")
async def request_session(
    body: RemoteSessionRequest,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> RemoteSessionRead:
    """Returns a pending session. Nothing is connected, and nothing will be until the
    person answers — poll this session's id to find out whether they did."""
    try:
        remote_session = await RemoteControlService(session).request(
            actor=actor, device_id=body.device_id, reason=body.reason,
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except SessionAlreadyOpenError as exc:
        # 409 rather than 400: the thing the caller wants is already happening. A plain
        # error invites a second click, and a second click puts a second consent prompt
        # on somebody's screen — which is how people learn to click Allow without reading.
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    except RemoteControlError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    # Label the endpoint's consent prompt with who is asking and why, before the link is
    # opened and the prompt appears. Best-effort inside the helper — never fails the request.
    await _label_consent(session, remote_session, actor)
    # With the link, because opening it is what puts the prompt on the person's screen.
    # Returning it here rather than making the portal poll for it once saves a round trip
    # on the one step where the technician is watching a spinner.
    return await _render(session, remote_session, actor=actor, include_viewer_url=True)


@router.get("/{session_id}", response_model=RemoteSessionRead,
            summary="How a request is going, and the link once it is accepted")
async def get_session(
    session_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> RemoteSessionRead:
    try:
        remote_session = await RemoteControlService(session).get(
            actor=actor, session_id=session_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    return await _render(session, remote_session, actor=actor, include_viewer_url=True)


@router.post("/{session_id}/end", response_model=RemoteSessionRead,
             summary="End a session")
async def end_session(
    session_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> RemoteSessionRead:
    """Idempotent: ending a session that has already finished returns it unchanged.

    Both sides can hang up at the same moment, and that race is ordinary — the person
    closing the banner as the technician clicks disconnect. Neither should see an error.
    """
    service = RemoteControlService(session)
    try:
        await service.get(actor=actor, session_id=session_id)
        remote_session = await service.end(session_id=session_id, actor=actor)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    return await _render(session, remote_session, actor=actor)


@router.get("", response_model=Page[RemoteSessionRead],
            summary="Remote sessions across the org")
async def list_sessions(
    device_id: uuid.UUID | None = None,
    status_filter: list[RemoteSessionStatus] | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> Page[RemoteSessionRead]:
    """The history, for the portal and for anyone asking what happened last Tuesday.

    No viewer links here, whatever the status. A list endpoint is read by a page that
    shows many sessions to whoever can see the page; minting credentials into it would
    scatter them.
    """
    page, page_size = clamp(page, page_size)
    rows, total = await RemoteControlService(session).list_page(
        actor=actor, device_id=device_id, status=status_filter,
        offset=(page - 1) * page_size, limit=page_size,
    )
    items = [await _render(session, row) for row in rows]
    return build(items, total, page, page_size)
