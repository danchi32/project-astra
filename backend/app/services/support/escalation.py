"""Handing an unsolved problem to a human, once.

Two rules carry this whole feature, and both are enforced here rather than asked for in a
prompt:

  **Ask first.** A ticket is raised only after ASTRA offered and the user answered. The
  offer is a row; raising checks for it. A model that decides to file a ticket on its own
  would be filing it in someone's real production queue.

  **Once per problem.** A user who reports the same thing three times — because nothing has
  visibly happened yet — must not produce three tickets. Duplicate tickets wreck the
  customer's SLA reporting, and an IT manager whose queue fills with them turns the
  integration off. That is the most common way an integration like this dies, so it is
  guarded before anything else.
"""
import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message, MessageRole, SupportEscalation
from app.models.base import utcnow
from app.models.support_escalation import EscalationState
from app.services.ai.embeddings import cosine_similarity, get_embedding_provider
from app.services.support.connector import TicketConnector, TicketError, TicketRequest
from app.services.support.dossier import Dossier

logger = logging.getLogger(__name__)

# How long a raised ticket suppresses a new one for the same problem. A working day: long
# enough to cover "I reported this morning and nothing has happened", short enough that a
# genuinely recurring fault next week opens a fresh ticket rather than being swallowed.
DEDUPE_WINDOW = timedelta(hours=24)

# How alike two complaints must be to count as the same problem. Deliberately not high:
# the cost of a false match is one deferred ticket and a message telling the user which
# ticket already exists; the cost of a miss is a duplicate in the customer's queue.
DEDUPE_SIMILARITY = 0.6


class ConsentMissing(RuntimeError):
    """raise_support_ticket was called without an outstanding offer the user answered."""


@dataclass
class RaiseOutcome:
    escalation: SupportEscalation
    created: bool          # False when an existing ticket already covered this
    message: str           # what the assistant should say, already true either way


class EscalationService:
    def __init__(self, session: AsyncSession, connector: TicketConnector | None = None) -> None:
        self.session = session
        self.connector = connector
        self.embed = get_embedding_provider()

    # -- Offering -----------------------------------------------------------

    async def offer(
        self,
        *,
        org_id: uuid.UUID,
        conversation_id: uuid.UUID | None,
        device_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
        dossier: Dossier,
        action_id: str | None = None,
    ) -> tuple[SupportEscalation | None, str]:
        """Record that ASTRA is offering to escalate, and return what to say.

        Returns (None, message) when an open ticket already covers this — the user is told
        which one rather than being asked a question whose answer would create a duplicate.
        """
        existing = await self._find_recent_ticket(
            org_id=org_id, device_id=device_id, user_id=user_id, problem=dossier.problem
        )
        if existing is not None:
            return None, self._already_raised_message(existing)

        vector = await self.embed.embed(dossier.problem, purpose="document")
        escalation = SupportEscalation(
            org_id=org_id, conversation_id=conversation_id, device_id=device_id,
            user_id=user_id, problem_summary=dossier.problem[:1000],
            embedding=vector, embedding_model=self.embed.name,
            action_id=action_id, dossier=dossier.to_html()[:20000],
            state=EscalationState.OFFERED,
        )
        self.session.add(escalation)
        await self.session.flush()
        return escalation, (
            "I wasn't able to fix this one myself. "
            "Shall I raise a ticket with your IT team?"
        )

    # -- Raising ------------------------------------------------------------

    async def raise_ticket(
        self, *, org_id: uuid.UUID, conversation_id: uuid.UUID, requester_email: str | None,
        priority: str = "low", category: str | None = None, sub_category: str | None = None,
    ) -> RaiseOutcome:
        """Raise the ticket the user just agreed to.

        Refuses unless there is an outstanding offer in this conversation AND the user has
        spoken since it was made. That second half is the actual gate: without it the model
        could call offer and raise back to back and never let a person answer.
        """
        escalation = await self._pending_offer(conversation_id)
        if escalation is None:
            raise ConsentMissing("No outstanding escalation offer in this conversation.")
        if not await self._user_replied_after(conversation_id, escalation):
            raise ConsentMissing("The user has not answered the escalation offer yet.")

        # Re-check between offer and answer: another device or another chat may have raised
        # this in the meantime, and the user's "yes" should not turn into a second ticket.
        existing = await self._find_recent_ticket(
            org_id=org_id, device_id=escalation.device_id, user_id=escalation.user_id,
            problem=escalation.problem_summary, exclude_id=escalation.id,
        )
        if existing is not None:
            escalation.state = EscalationState.DECLINED
            escalation.last_error = "superseded by an existing ticket"
            await self.session.flush()
            return RaiseOutcome(existing, created=False,
                                message=self._already_raised_message(existing))

        if self.connector is None:
            escalation.state = EscalationState.FAILED
            escalation.last_error = "no helpdesk configured for this organization"
            await self.session.flush()
            return RaiseOutcome(escalation, created=False, message=(
                "I couldn't raise the ticket — no helpdesk is connected for your "
                "organization yet. I've let your IT team know."
            ))

        request = TicketRequest(
            requester_email=requester_email or "",
            subject=Dossier(problem=escalation.problem_summary).subject(),
            description_html=escalation.dossier or escalation.problem_summary,
            priority=priority, category=category, sub_category=sub_category,
        )
        try:
            result = await self.connector.create_ticket(request)
        except TicketError as exc:
            # Never report a ticket that does not exist. The user would wait for a reply
            # nobody is coming to write.
            escalation.state = EscalationState.FAILED
            escalation.last_error = str(exc)[:500]
            await self.session.flush()
            logger.warning("Escalation %s could not be filed: %s", escalation.id, exc)
            return RaiseOutcome(escalation, created=False, message=(
                "I couldn't reach your IT helpdesk just now, so the ticket isn't raised "
                "yet. I've flagged this for your IT team."
            ))

        escalation.state = EscalationState.RAISED
        escalation.provider = self.connector.name
        escalation.external_ticket_id = result.external_id
        escalation.external_url = result.url
        escalation.raised_at = utcnow()
        await self.session.flush()
        return RaiseOutcome(escalation, created=True, message=(
            f"Done — I've raised ticket #{result.external_id} with your IT team. "
            "Someone from support will reach out to you shortly."
        ))

    async def decline(self, *, conversation_id: uuid.UUID) -> None:
        escalation = await self._pending_offer(conversation_id)
        if escalation is not None:
            escalation.state = EscalationState.DECLINED
            await self.session.flush()

    # -- Internals ----------------------------------------------------------

    async def _pending_offer(self, conversation_id: uuid.UUID) -> SupportEscalation | None:
        result = await self.session.execute(
            select(SupportEscalation)
            .where(
                SupportEscalation.conversation_id == conversation_id,
                SupportEscalation.state == EscalationState.OFFERED,
            )
            .order_by(SupportEscalation.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def _user_replied_after(
        self, conversation_id: uuid.UUID, escalation: SupportEscalation
    ) -> bool:
        result = await self.session.execute(
            select(Message.id)
            .where(
                Message.conversation_id == conversation_id,
                Message.role == MessageRole.USER,
                Message.created_at >= escalation.created_at,
            )
            .limit(1)
        )
        return result.scalars().first() is not None

    async def _find_recent_ticket(
        self, *, org_id: uuid.UUID, device_id: uuid.UUID | None, user_id: uuid.UUID | None,
        problem: str, exclude_id: uuid.UUID | None = None,
    ) -> SupportEscalation | None:
        """An open ticket for the same problem, raised recently.

        Scoped to the same device or the same person — a problem is theirs, not the
        organization's, and suppressing across an entire org would hide real tickets.
        """
        if device_id is None and user_id is None:
            return None

        stmt = (
            select(SupportEscalation)
            .where(
                SupportEscalation.org_id == org_id,
                SupportEscalation.state == EscalationState.RAISED,
                SupportEscalation.created_at >= utcnow() - DEDUPE_WINDOW,
            )
            .order_by(SupportEscalation.created_at.desc())
        )
        if device_id is not None:
            stmt = stmt.where(SupportEscalation.device_id == device_id)
        else:
            stmt = stmt.where(SupportEscalation.user_id == user_id)
        if exclude_id is not None:
            stmt = stmt.where(SupportEscalation.id != exclude_id)

        candidates = list((await self.session.execute(stmt)).scalars())
        if not candidates:
            return None

        vector = await self.embed.embed(problem, purpose="query")
        for candidate in candidates:
            # A vector from another provider is incomparable, not merely a weak match —
            # skip rather than score it at a meaningless zero.
            if candidate.embedding_model != self.embed.name or not candidate.embedding:
                continue
            if cosine_similarity(vector, candidate.embedding) >= DEDUPE_SIMILARITY:
                return candidate
        return None

    @staticmethod
    def _already_raised_message(escalation: SupportEscalation) -> str:
        return (
            f"You already have ticket #{escalation.external_ticket_id} open with IT for "
            "this. Support will get back to you on that one — I haven't raised another."
        )
