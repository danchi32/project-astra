"""Requesting, watching and ending a remote session.

Three endpoints and one rule that shapes all of them: the viewer URL is a CREDENTIAL. It
logs its bearer into the relay as the technician and puts them on a named device, so it
is minted per request, handed only to the person who asked, and never written to the
database. A column holding these would be a table of live keys to other people's screens.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles, requires
from app.core.database import get_db
from app.models import Device, RemoteSession, RemoteSessionStatus, User, UserRole
from app.models.base import as_utc, utcnow
from app.schemas.pagination import Page, build, clamp
from app.schemas.remote_control import RemoteSessionRead, RemoteSessionRequest
from app.services.entitlements import REMOTE_CONTROL
from app.services.exceptions import NotFoundError
from app.services.meshcentral import MeshCentralClient, MeshCentralNotConfigured
from app.services.remote_control import (
    CONSENT_TIMEOUT,
    RemoteControlError,
    RemoteControlService,
    SessionAlreadyOpenError,
)

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

    # The link appears only once the person at the device has agreed, and only for the
    # technician who asked. Both halves matter: before consent there is nothing to look
    # at, and handing it to a colleague would be handing over the session itself.
    if (
        include_viewer_url
        and actor is not None
        and remote_session.requested_by_user_id == actor.id
        and remote_session.status in (RemoteSessionStatus.APPROVED,
                                      RemoteSessionStatus.ACTIVE)
        and device is not None
        and device.meshcentral_node_id
    ):
        client = MeshCentralClient()
        try:
            out.viewer_url = client.viewer_url(
                node_id=device.meshcentral_node_id,
                user_id=client.user or "",
            )
        except MeshCentralNotConfigured:
            # The session is real and its record stands; there is just no relay to show
            # it through. Leaving the field empty says exactly that.
            out.viewer_url = None
    return out


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
    return await _render(session, remote_session, actor=actor)


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
