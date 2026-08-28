import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.database import get_db
from app.models import User, UserRole
from app.schemas.remediation import RemediationTaskRead
from app.schemas.sessions import DeviceSessionPage, DeviceSessionRead
from app.services.exceptions import NotFoundError
from app.services.remediation.service import AlreadyQueuedError, RemediationError
from app.services.sessions import SESSION_ACTIONS, SessionService

router = APIRouter(prefix="/sessions", tags=["sessions"])

# Reading who is signed in where is staff work, not everyone's. A regular user has no
# business enumerating their colleagues' desktops, and this endpoint would be the neatest
# way to do it.
staff_required = require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)


class SessionActionRequest(BaseModel):
    """One action against one session.

    `action_id` names an entry in the remediation registry, so the tier attached to it there
    is what decides who may push it — this endpoint accepting the request is not the
    authorisation. Passing an id that is not a session action is a 404, not a tier error,
    because "restart_explorer with a session id" is a client bug and should read as one.
    """
    device_id: uuid.UUID
    action_id: str
    session_id: int = Field(ge=0)
    # message_session only.
    message: str | None = Field(default=None, max_length=1000)
    # reset_local_password only. The portal prefills it from the session's own username;
    # it is sent explicitly because the account and the session are not the same thing and
    # the caller should have to say which account they mean.
    username: str | None = Field(default=None, max_length=150)
    reason: str | None = Field(default=None, max_length=500)


@router.get("", response_model=DeviceSessionPage,
            summary="Every logon session across the fleet")
async def list_sessions(
    q: str | None = Query(default=None, max_length=100),
    state: str | None = Query(default=None, pattern="^(active|disconnected)$"),
    connection: str | None = Query(default=None, pattern="^(console|rdp)$"),
    group_id: uuid.UUID | None = None,
    online: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> DeviceSessionPage:
    return await SessionService(session).list_page(
        actor=actor, q=q, state=state, connection=connection, group_id=group_id,
        online=online, page=page, page_size=page_size,
    )


@router.post("/actions", response_model=RemediationTaskRead,
             summary="Lock, sign out, message, or reset a password on one session")
async def act_on_session(
    body: SessionActionRequest,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> RemediationTaskRead:
    """Queue a session action.

    Staff may reach this endpoint; the ACTION's tier decides whether they may actually run
    it. Sign-out and password reset are admin-only and a technician calling this gets the
    same refusal they would get from the approval queue — the check lives in one place, in
    RemediationService, so there is no second answer to disagree with.
    """
    try:
        task = await SessionService(session).act(
            actor=actor,
            device_id=body.device_id,
            action_id=body.action_id,
            session_id=body.session_id,
            message=body.message,
            username=body.username,
            reason=body.reason,
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except AlreadyQueuedError as exc:
        # Not a failure: the work the caller wants is already happening. A 400 here would
        # read as "that didn't go through" and invite them to click again, which is how the
        # duplicate they are being protected from gets created.
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    except RemediationError as exc:
        # Every refusal these can raise is worth reading: "session 0 is the services
        # session", "your role cannot approve a task at this trust tier", "a message is
        # required". Letting them escape as a 500 would replace all of that with
        # "Internal Server Error" and leave the operator with nothing to act on.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return RemediationTaskRead.model_validate(task)


@router.get("/actions/available", response_model=list[str],
            summary="Session action ids this build supports")
async def available_actions(
    actor: User = Depends(staff_required),
) -> list[str]:
    """So the portal renders the buttons this backend can actually honour rather than a
    hardcoded list that drifts from it after a deploy."""
    return sorted(SESSION_ACTIONS)


@router.get("/device/{device_id}", response_model=list[DeviceSessionRead],
            summary="Sessions on one device")
async def device_sessions(
    device_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> list[DeviceSessionRead]:
    try:
        return await SessionService(session).for_device(actor=actor, device_id=device_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
