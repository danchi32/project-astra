from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

import uuid

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
from app.schemas.remediation import AgentRemediationResult, AgentRemediationTask
from app.services.conversations import ConversationService
from app.services.devices import DeviceService
from app.services.remediation.service import RemediationService

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


@router.get(
    "/tasks",
    response_model=list[AgentRemediationTask],
    summary="Claim approved remediation tasks to execute (agent only)",
)
async def claim_tasks(
    device: Device = Depends(get_current_device),
    session: AsyncSession = Depends(get_db),
) -> list[AgentRemediationTask]:
    tasks = await RemediationService(session).claim_for_device(device=device)
    return [
        AgentRemediationTask(id=t.id, action_id=t.action_id, params=t.params) for t in tasks
    ]


@router.post(
    "/tasks/{task_id}/result",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Report the result of a remediation task (agent only)",
)
async def report_task_result(
    task_id: uuid.UUID,
    body: AgentRemediationResult,
    device: Device = Depends(get_current_device),
    session: AsyncSession = Depends(get_db),
) -> None:
    await RemediationService(session).record_result(
        device=device, task_id=task_id, success=body.success, output=body.output
    )
