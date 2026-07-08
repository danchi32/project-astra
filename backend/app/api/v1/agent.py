from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_device
from app.core.database import get_db
from app.models import Device
from app.schemas.conversations import AgentChatRequest, AgentChatResponse
from app.schemas.devices import (
    EnrollRequest,
    EnrollResponse,
    HeartbeatRequest,
    HeartbeatResponse,
)
from app.services.conversations import ConversationService
from app.services.devices import DeviceService

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/enroll", response_model=EnrollResponse, summary="Enroll a device")
async def enroll(body: EnrollRequest, session: AsyncSession = Depends(get_db)) -> EnrollResponse:
    device, device_token = await DeviceService(session).enroll(body)
    return EnrollResponse(device_id=device.id, device_token=device_token)


@router.post("/heartbeat", response_model=HeartbeatResponse, summary="Report device liveness")
async def heartbeat(
    body: HeartbeatRequest,
    device: Device = Depends(get_current_device),
    session: AsyncSession = Depends(get_db),
) -> HeartbeatResponse:
    await DeviceService(session).heartbeat(device=device, data=body)
    return HeartbeatResponse()


@router.post(
    "/chat",
    response_model=AgentChatResponse,
    summary="Chat with ASTRA from the device tray (device-authenticated)",
)
async def chat(
    body: AgentChatRequest,
    device: Device = Depends(get_current_device),
    session: AsyncSession = Depends(get_db),
) -> AgentChatResponse:
    conversation, assistant = await ConversationService(session).device_chat(
        device=device, content=body.content, conversation_id=body.conversation_id
    )
    return AgentChatResponse(
        conversation_id=conversation.id,
        reply=assistant.content,
        tool_trail=assistant.tool_trail,
    )
