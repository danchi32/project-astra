import logging

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

import uuid

from app.api.deps import get_rate_limited_device
from app.core.database import get_db
from app.models import Device
from app.schemas.conversations import (
    AgentChatRequest,
    AgentChatResponse,
    AgentConversationHistory,
    AgentHistoryMessage,
)
from app.core.config import get_settings
from app.schemas.devices import (
    AgentUpdateEnvelope,
    EnrollRequest,
    EnrollResponse,
    HeartbeatRequest,
    HeartbeatResponse,
)
from app.schemas.devices import RemoteSupportPlan, REMOTE_SUPPORT_SERVICE_NAME
from app.schemas.remediation import AgentRemediationResult, AgentRemediationTask
from app.schemas.telemetry import ActivityPush, TelemetryPushResponse
from app.services.agent_update import AgentUpdateService
from app.services.conversations import ConversationService
from app.services.devices import DeviceService
from app.services.remediation.service import RemediationService
from app.services.workforce import WorkforceAggregator

logger = logging.getLogger("astra.agent")

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/enroll", response_model=EnrollResponse, summary="Enroll a device")
async def enroll(body: EnrollRequest, session: AsyncSession = Depends(get_db)) -> EnrollResponse:
    device, device_token = await DeviceService(session).enroll(body)
    return EnrollResponse(device_id=device.id, device_token=device_token)


@router.post("/heartbeat", response_model=HeartbeatResponse, summary="Report device liveness")
async def heartbeat(
    body: HeartbeatRequest,
    device: Device = Depends(get_rate_limited_device),
    session: AsyncSession = Depends(get_db),
) -> HeartbeatResponse:
    await DeviceService(session).heartbeat(device=device, data=body)

    # Whether this org may collect Workforce Insights ("Tracker") activity, and how much of a
    # browser URL it records. The agent reads both to decide what to collect; the tray reads
    # the tracking flag (via the agent) to show "Activity tracking: ON" — the server deciding
    # keeps the agent from tracking covertly.
    tracking, url_mode = await _activity_settings(session, device.org_id)

    # Piggyback the elevated Service's work on the beat it already sends, so it needs no
    # separate 30s poll — roughly a fifth of all agent traffic. Strictly opt-in: claiming
    # marks a task dispatched, so handing tasks to an agent that doesn't read them would take
    # the work away from the poller it still depends on and self-healing would stop.
    #
    # Only "system" context here. The user-context Tray is a different process and claims its
    # own tasks; returning those here would steal them from it.
    if not body.include_tasks:
        return HeartbeatResponse(activity_tracking=tracking, activity_url_mode=url_mode)

    tasks = await RemediationService(session).claim_for_device(device=device, context="system")
    return HeartbeatResponse(
        tasks=[AgentRemediationTask(id=t.id, action_id=t.action_id, params=t.params) for t in tasks],
        activity_tracking=tracking,
        activity_url_mode=url_mode,
    )


@router.post(
    "/activity",
    response_model=TelemetryPushResponse,
    summary="Submit Workforce Insights activity events (agent/tray only)",
)
async def push_activity(
    body: ActivityPush,
    background: BackgroundTasks,
    device: Device = Depends(get_rate_limited_device),
    session: AsyncSession = Depends(get_db),
) -> TelemetryPushResponse:
    """The Tray's channel for foreground app/website samples. Stored and aggregated only when
    the org holds the workforce_insights entitlement; a stray payload from an untracked org is
    dropped (the same gate the Service's telemetry push applies to activity)."""
    if body.activity and await WorkforceAggregator.enabled_for(session, device.org_id):
        await WorkforceAggregator(session).ingest_events(device=device, events=body.activity)
        await session.commit()
        # After the beat is stored and acknowledged, let the AI categorise any app/site the
        # built-in taxonomy and the global learned store don't yet cover. Off the response path,
        # best-effort, and a no-op when there is nothing new or no AI key is configured.
        background.add_task(_classify_new_activity_bg, device.org_id)
    return TelemetryPushResponse()


async def _classify_new_activity_bg(org_id: uuid.UUID) -> None:
    """Run the workforce AI classifier in its own session, swallowing any error — a failed
    categorisation must never surface to the agent or leave the request half-committed."""
    from app.core.database import SessionLocal
    from app.services.workforce_ai import classify_new_activity

    try:
        async with SessionLocal() as session:
            await classify_new_activity(session, org_id)
    except Exception:  # noqa: BLE001 — best-effort; the next beat retries.
        logger.exception("workforce AI classification failed for org %s", org_id)


async def _activity_settings(session: AsyncSession, org_id: uuid.UUID) -> tuple[bool, str]:
    """(tracking enabled, url mode) for this org. A lookup miss is (False, "domain") — the safe
    failure for monitoring is NOT to collect, unlike remote support, which fails the other way
    to avoid stripping a working feature during an outage."""
    from app.models import Organization
    from app.services.entitlements import WORKFORCE_INSIGHTS, features_for

    org = await session.get(Organization, org_id)
    if org is None:
        return False, "domain"
    tracking = WORKFORCE_INSIGHTS in features_for(org.plan, org.entitlement_overrides)
    url_mode = "path" if org.workforce_url_mode == "path" else "domain"
    return tracking, url_mode


@router.get(
    "/update",
    response_model=AgentUpdateEnvelope,
    summary="Get the current signed agent-update manifest (device-authenticated)",
)
async def get_update(
    device: Device = Depends(get_rate_limited_device),
) -> AgentUpdateEnvelope:
    # The backend only relays an already-signed manifest; the agent verifies it against a
    # pinned key, so this endpoint is not itself a trust boundary for update integrity.
    current = await AgentUpdateService(get_settings()).current()
    if current is None:
        return AgentUpdateEnvelope(available=False)
    manifest, signature = current
    return AgentUpdateEnvelope(available=True, manifest=manifest, signature=signature)


@router.post(
    "/chat",
    response_model=AgentChatResponse,
    summary="Chat with ASTRA from the device tray (device-authenticated)",
)
async def chat(
    body: AgentChatRequest,
    device: Device = Depends(get_rate_limited_device),
    session: AsyncSession = Depends(get_db),
) -> AgentChatResponse:
    conversation, assistant, source = await ConversationService(session).device_chat(
        device=device, content=body.content, conversation_id=body.conversation_id
    )
    return AgentChatResponse(
        conversation_id=conversation.id,
        reply=assistant.content,
        tool_trail=assistant.tool_trail,
        source=source,
    )


@router.get(
    "/conversation",
    response_model=AgentConversationHistory,
    summary="Get this device's most recent conversation so the tray can restore it",
)
async def conversation_history(
    device: Device = Depends(get_rate_limited_device),
    session: AsyncSession = Depends(get_db),
) -> AgentConversationHistory:
    conversation_id, messages = await ConversationService(session).device_history(device=device)
    return AgentConversationHistory(
        conversation_id=conversation_id,
        messages=[AgentHistoryMessage(role=r, content=c) for r, c in messages],
    )


@router.get(
    "/tasks",
    response_model=list[AgentRemediationTask],
    summary="Claim approved remediation tasks to execute (agent only)",
)
async def claim_tasks(
    context: str = "user",
    device: Device = Depends(get_rate_limited_device),
    session: AsyncSession = Depends(get_db),
) -> list[AgentRemediationTask]:
    # context selects which agent process is claiming: "user" (desktop Tray) or "system"
    # (elevated Service). Each only ever receives the tasks it has the privilege to run.
    tasks = await RemediationService(session).claim_for_device(device=device, context=context)
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
    device: Device = Depends(get_rate_limited_device),
    session: AsyncSession = Depends(get_db),
) -> None:
    await RemediationService(session).record_result(
        device=device, task_id=task_id, success=body.success, output=body.output
    )


@router.get(
    "/remote-support",
    response_model=RemoteSupportPlan,
    summary="Whether this device should run the remote-support agent, and where to get it",
)
async def remote_support_plan(
    device: Device = Depends(get_rate_limited_device),
    session: AsyncSession = Depends(get_db),
) -> RemoteSupportPlan:
    """What the device should do about remote support, decided here rather than there.

    Nothing about remote support ships in the ASTRA installer. A device asks this, and
    only installs the relay agent if the answer says so — which means a customer who has
    not bought remote control never receives a remote-access executable at all, rather
    than receiving one that sits unused on every machine they own.

    `enabled: false` is an instruction too. A device already running the relay agent
    uninstalls it when the answer turns false, so withdrawing the feature actually
    withdraws it from the fleet instead of leaving it installed and merely unreachable.

    Three things must all hold for `enabled: true` — a relay configured on this
    deployment, the org's plan including remote control, and an operator having created a
    device group for this org on that relay. They fail differently and none of them
    implies the others.
    """
    from app.models import Organization
    from app.services.entitlements import REMOTE_CONTROL, features_for
    from app.services.meshcentral import MeshCentralClient

    client = MeshCentralClient()
    org = await session.get(Organization, device.org_id)

    if org is None or not client.configured or not org.meshcentral_mesh_id:
        return RemoteSupportPlan(enabled=False)
    if REMOTE_CONTROL not in features_for(org.plan, org.entitlement_overrides):
        return RemoteSupportPlan(enabled=False)

    return RemoteSupportPlan(
        enabled=True,
        download_url=client.agent_download_url(org.meshcentral_mesh_id),
        service_name=REMOTE_SUPPORT_SERVICE_NAME,
    )
