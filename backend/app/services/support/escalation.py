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
import re
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Message, MessageRole, SupportEscalation
from app.models.base import utcnow
from app.models.support_escalation import EscalationState
from app.services.ai.embeddings import cosine_similarity, get_embedding_provider
from app.services.audit import AuditService
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


# What counts as answering the offer. Checked in code because the alternative is trusting
# the model to have read the reply correctly — and the model is the part of this system an
# attacker can reach, through telemetry, event-log strings and knowledge articles that all
# land in its context. Refusals are matched first: "no, don't bother" contains neither an
# agreement token nor anything ambiguous, but "no thanks, ok" would otherwise pass.
_REFUSAL = re.compile(
    # `don'?t` rather than `dont`: an apostrophe is a word boundary, so \bdont\b would
    # miss the spelling people actually type.
    r"\b(no|nope|nah|don'?t|do not|cancel|skip|leave it|forget it|not now|later|"
    r"nahi|nahin|nhi|naa|mat|rehne do|rahne do|baad me|baad mein|zarurat nahi)\b",
)

# Agreement has to be the whole reply, not a word inside one. The offer is posted when a
# fix fails and then sits open for the rest of the conversation, so the next message is far
# more likely to be a follow-up request than an answer — and "please run the disk cleanup
# instead" or "ok so outlook is still crashing" would otherwise file a ticket while the
# user was asking for something else entirely.
_YES = re.compile(
    r"^\W*(yes|yeah|yep|yup|ya|ok|okay|sure|go ahead|do it|please do|"
    r"ji haan|haan|haa|han|hn|ji|theek hai|thik hai|bilkul|zaroor|zarur|"
    r"kar do|kardo|kr do|kro|karo|kar dijiye)"
    r"(\s+(please|thanks|thank you|yes|haan|ji|na|bhai|yaar|go ahead|do it|"
    r"kar do|kardo|karo|kro))*"
    r"\W*\Z"
)
# The one form that is unambiguous wherever it appears: naming the thing being agreed to.
_YES_EXPLICIT = re.compile(
    r"\b(raise (it|one|a ticket|the ticket)|ticket (raise|bana)\s?(kar\s?)?do)\b"
)


def _is_agreement(answer: str) -> bool:
    return bool(_YES.match(answer) or _YES_EXPLICIT.search(answer))


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
        priority: str | None = None, category: str | None = None,
        sub_category: str | None = None,
    ) -> RaiseOutcome:
        """Raise the ticket the user just agreed to.

        Refuses unless there is an outstanding offer in this conversation AND the user has
        agreed to it in so many words. "The user said something" is not the gate: an offer
        raised after a failed remediation sits open for as long as the conversation does,
        and the next message of any content would otherwise open it.
        """
        escalation = await self._pending_offer(conversation_id)
        if escalation is None:
            raise ConsentMissing("No outstanding escalation offer in this conversation.")

        answer = await self._answer_to(conversation_id, escalation)
        if answer is None:
            raise ConsentMissing("The user has not answered the escalation offer yet.")
        if _REFUSAL.search(answer):
            # Close it rather than leaving it open for a later message to reopen.
            escalation.state = EscalationState.DECLINED
            await self.session.flush()
            raise ConsentMissing("The user declined the offer to raise a ticket.")
        if not _is_agreement(answer):
            raise ConsentMissing(
                "The user's reply was neither a yes nor a no — ask them plainly whether "
                "to raise a ticket before calling this again."
            )

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
        # Written before the call, not after. Creating a ticket in someone else's system is
        # not undoable, so the row that records it must already be in the transaction — if
        # it were added afterwards and its flush failed, the transaction would roll back
        # and leave a real ticket in the customer's queue with nothing here to show for it.
        entry = await self._audit(escalation, org_id=org_id, requester=requester_email)

        try:
            result = await self.connector.create_ticket(request)
        except TicketError as exc:
            # Never report a ticket that does not exist. The user would wait for a reply
            # nobody is coming to write.
            escalation.state = EscalationState.FAILED
            escalation.last_error = str(exc)[:500]
            entry.action = "helpdesk.ticket.failed"
            entry.detail = {**entry.detail, "error": escalation.last_error}
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
        entry.detail = {**entry.detail, "ticket_id": result.external_id}
        # Any other offer still open in this conversation was answered by the same "yes".
        # Left alone, the model could raise each of them in turn on one consent.
        await self._close_other_offers(conversation_id, keep=escalation.id)
        await self.session.flush()
        return RaiseOutcome(escalation, created=True, message=(
            f"Done — I've raised ticket #{result.external_id} with your IT team. "
            "Someone from support will reach out to you shortly."
        ))

    async def pending_offer(self, conversation_id: uuid.UUID) -> SupportEscalation | None:
        """The outstanding offer in this conversation, if any. Callers need it to know
        which action was tried, so the ticket can be filed under the right category."""
        return await self._pending_offer(conversation_id)

    async def decline(self, *, conversation_id: uuid.UUID) -> None:
        escalation = await self._pending_offer(conversation_id)
        if escalation is not None:
            escalation.state = EscalationState.DECLINED
            await self.session.flush()

    # -- Internals ----------------------------------------------------------

    async def _audit(
        self, escalation: SupportEscalation, *, org_id: uuid.UUID, requester: str | None,
    ) -> AuditLog:
        """Record that ASTRA is creating a record in someone else's system, on a named
        employee's behalf, carrying that employee's device telemetry.

        The escalation row is the business record; this is the audit trail. The caller here
        is the model's tool loop, which is exactly the caller that most needs an entry it
        cannot choose to skip. Returned so the outcome can be written onto it once known.
        """
        return await AuditService(self.session).record(
            org_id=org_id,
            actor_id=escalation.user_id,
            action="helpdesk.ticket.raised",
            target_type="support_escalation",
            target_id=str(escalation.id),
            detail={
                "provider": self.connector.name if self.connector else None,
                "device_id": str(escalation.device_id) if escalation.device_id else None,
                "requester": requester,
                "action_tried": escalation.action_id,
            },
        )

    async def _close_other_offers(self, conversation_id: uuid.UUID, *, keep: uuid.UUID) -> None:
        rows = (await self.session.execute(
            select(SupportEscalation).where(
                SupportEscalation.conversation_id == conversation_id,
                SupportEscalation.state == EscalationState.OFFERED,
                SupportEscalation.id != keep,
            )
        )).scalars().all()
        for row in rows:
            row.state = EscalationState.DECLINED
            row.last_error = "superseded — the user's answer raised a different ticket"

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

    async def _answer_to(
        self, conversation_id: uuid.UUID, escalation: SupportEscalation
    ) -> str | None:
        """The first thing the user said after the offer, lowercased. None if they haven't.

        The *first* reply, not the latest: it is the one that answered the question. Taking
        the latest would let a conversation that has moved on to something else supply a
        stray "ok" as consent to a ticket nobody is still thinking about.
        """
        result = await self.session.execute(
            select(Message.content)
            .where(
                Message.conversation_id == conversation_id,
                Message.role == MessageRole.USER,
                Message.created_at >= escalation.created_at,
            )
            .order_by(Message.created_at.asc())
            .limit(1)
        )
        answer = result.scalars().first()
        return answer.lower() if answer else None

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
