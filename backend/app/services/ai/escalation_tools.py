"""The two tools that let a conversation reach the escalation path.

They are advertised to the model only when the organization can actually file a ticket —
a configured helpdesk, a decryptable credential, and a requester we can name. Every one of
those missing is a reason not to offer: asking "shall I raise a ticket?" and then failing
is worse than never asking, because by then the user believes help is coming.

Consent is not requested of the model, it is enforced underneath it. `raise_support_ticket`
checks the offer row and checks that a person has spoken since — see EscalationService.
"""
import json
import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.support import factory, requester
from app.services.support.dossier import Dossier
from app.services.support.escalation import ConsentMissing, EscalationService

logger = logging.getLogger(__name__)

OFFER = "offer_support_ticket"
RAISE = "raise_support_ticket"

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": OFFER,
        "description": (
            "Offer to raise a support ticket with the organization's IT helpdesk. Use this "
            "ONLY when you have genuinely run out of things to try: a fix you applied did "
            "not work, no fix exists for the problem, or the user says the problem is still "
            "there after a successful fix. Do not use it as a first response, and do not "
            "use it for questions you can answer. This tool asks the user — it does not "
            "raise anything. Wait for their reply."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "problem": {
                    "type": "string",
                    "description": "The user's own description of the problem, in their "
                    "words rather than your summary of it.",
                },
                "action_tried": {
                    "type": "string",
                    "description": "The action_id of the fix you attempted, if any.",
                },
            },
            "required": ["problem"],
        },
    },
    {
        "name": RAISE,
        "description": (
            "Raise the support ticket you already offered, after the user has agreed. Only "
            "call this once they have answered yes. If they declined, do not call it."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
]


async def available_for(
    session: AsyncSession, *, org_id: uuid.UUID, conversation_id: uuid.UUID | None,
    device_id: uuid.UUID | None,
) -> list[dict[str, Any]]:
    """The escalation tools, or nothing at all.

    Withholding the tool is the guard. A model that cannot see it cannot promise a ticket
    the organization has no way to file.
    """
    connector = await factory.build_connector(session, org_id)
    if connector is None:
        return []
    who = await requester.resolve(
        session, org_id=org_id, conversation_id=conversation_id, device_id=device_id
    )
    if who is None:
        return []
    return TOOL_SCHEMAS


async def dispatch(
    *, session: AsyncSession, org_id: uuid.UUID, name: str, tool_input: dict[str, Any] | None,
    conversation_id: uuid.UUID | None, device_id: uuid.UUID | None,
) -> str | None:
    """Handle an escalation tool call. Returns None when `name` is not one of ours."""
    if name not in (OFFER, RAISE):
        return None
    if conversation_id is None:
        # Both tools are anchored to a conversation: the offer lives in one, and consent is
        # "the user spoke in this conversation after it".
        return json.dumps({"error": "Escalation is only available inside a conversation."})

    connector = await factory.build_connector(session, org_id)
    settings = await factory.get_settings_for(session, org_id)
    service = EscalationService(session, connector=connector)
    who = await requester.resolve(
        session, org_id=org_id, conversation_id=conversation_id, device_id=device_id
    )

    if name == OFFER:
        problem = (tool_input or {}).get("problem") or ""
        if not problem.strip():
            return json.dumps({"error": "A problem description is required."})
        escalation, message = await service.offer(
            org_id=org_id, conversation_id=conversation_id, device_id=device_id,
            user_id=who.user_id if who else None,
            dossier=Dossier(problem=problem),
            action_id=(tool_input or {}).get("action_tried"),
        )
        await session.commit()
        return json.dumps({
            "asked": escalation is not None,
            "say_to_user": message,
        })

    # RAISE — file under the category this org mapped to the action ASTRA tried.
    offered = await service.pending_offer(conversation_id)
    category, sub_category = factory.category_for(
        settings, offered.action_id if offered else None
    )
    try:
        outcome = await service.raise_ticket(
            org_id=org_id, conversation_id=conversation_id,
            requester_email=who.email if who else None,
            # No priority: the org's configured default wins. ASTRA files at the level its
            # admin chose rather than judging how urgent someone else's problem is.
            category=category, sub_category=sub_category,
        )
    except ConsentMissing as exc:
        # Committed, not rolled back: a refusal closes the offer, and that has to survive
        # the turn or the next message would find it open again.
        await session.commit()
        # The model got ahead of the user. Reported back to it rather than raised, so it
        # can ask properly instead of the turn failing.
        return json.dumps({"raised": False, "error": str(exc),
                           "say_to_user": "Shall I raise a ticket with your IT team?"})
    await session.commit()
    return json.dumps({
        "raised": outcome.created,
        "ticket": outcome.escalation.external_ticket_id,
        "say_to_user": outcome.message,
    })
