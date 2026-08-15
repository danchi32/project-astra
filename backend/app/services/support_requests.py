"""Customers asking ASTRA for help, and ASTRA answering.

The diagnostics capture is the reason this exists inside the product rather than as a
mailto: link. Everything needed to understand a support request is already in this
database — what they pay for, how big the fleet is, how much of it is actually reporting
in, which agent builds are deployed, what has been failing. Attaching it at submit time
turns "it doesn't work" into a request somebody can act on without a round trip.
"""
import uuid

from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Device,
    Organization,
    RemediationStatus,
    RemediationTask,
    SupportRequest,
    SupportRequestMessage,
    SupportRequestPriority,
    SupportRequestStatus,
    User,
    UserRole,
)
from app.models.base import utcnow
from app.models.notification import NotificationCategory, NotificationSeverity
from app.schemas.devices import ONLINE_THRESHOLD
from app.services.audit import AuditService
from app.services.exceptions import NotFoundError, ValidationError
from app.services.notifications import NotificationService

#: How many characters of a uuid make the human-quotable reference. Six hex characters is
#: 16 million values — collisions are checked for anyway, this only decides how often the
#: check has to retry.
_REF_LEN = 6


def _reference() -> str:
    return f"SUP-{uuid.uuid4().hex[:_REF_LEN].upper()}"


class SupportRequestService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    # -- customer side --------------------------------------------------------

    async def create(
        self, *, actor: User, subject: str, body: str, category: str | None = None,
        priority: SupportRequestPriority = SupportRequestPriority.NORMAL,
    ) -> SupportRequest:
        """Open a request, with the state of their world attached."""
        if not subject.strip() or not body.strip():
            raise ValidationError("A subject and a description are both required")

        # Urgency is the customer's opinion of their own problem, and they are entitled to
        # it — but "urgent" is the operator's scheduling decision, so it is not offered
        # here. The highest a customer can set themselves is high.
        if priority is SupportRequestPriority.URGENT:
            priority = SupportRequestPriority.HIGH

        reference = await self._unique_reference()
        request = SupportRequest(
            org_id=actor.org_id, created_by_user_id=actor.id, reference=reference,
            subject=subject.strip(), category=category,
            status=SupportRequestStatus.OPEN, priority=priority,
            diagnostics=await self._diagnostics(actor.org_id),
        )
        self.session.add(request)
        await self.session.flush()

        self.session.add(SupportRequestMessage(
            request_id=request.id, author_user_id=actor.id, from_operator=False,
            body=body.strip(),
        ))
        request.last_reply_at = utcnow()

        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="support_request.create",
            target_type="support_request", target_id=str(request.id),
            detail={"reference": reference, "subject": request.subject},
        )
        await self.session.commit()
        return request

    async def reply(
        self, *, actor: User, request_id: uuid.UUID, body: str, from_operator: bool = False
    ) -> SupportRequestMessage:
        """Add a message. The status moves on its own, because a support queue where
        somebody has to remember to set the state is a queue that lies."""
        if not body.strip():
            raise ValidationError("A message cannot be empty")
        request = await self._get_for(actor, request_id, operator=from_operator)

        message = SupportRequestMessage(
            request_id=request.id, author_user_id=actor.id,
            from_operator=from_operator, body=body.strip(),
        )
        self.session.add(message)
        request.last_reply_at = utcnow()

        if from_operator:
            # We answered: it is theirs now — unless it was already finished, in which case
            # a note does not reopen it.
            if request.status not in (SupportRequestStatus.RESOLVED, SupportRequestStatus.CLOSED):
                request.status = SupportRequestStatus.WAITING_CUSTOMER
            await NotificationService(self.session).notify(
                org_id=request.org_id,
                category=NotificationCategory.SYSTEM,
                severity=NotificationSeverity.INFO,
                title=f"ASTRA support replied — {request.reference}",
                message=request.subject,
                link="/help",
            )
        else:
            # They answered: back to us. A customer replying to something marked resolved
            # is telling us it was not.
            request.status = SupportRequestStatus.OPEN
            request.resolved_at = None

        await self.audit.record(
            org_id=request.org_id, actor_id=actor.id,
            action="support_request.reply",
            target_type="support_request", target_id=str(request.id),
            detail={"reference": request.reference, "from_operator": from_operator},
        )
        await self.session.commit()
        return message

    async def list_for_org(
        self, *, actor: User, status: SupportRequestStatus | None = None
    ) -> list[SupportRequest]:
        """What this person is allowed to see.

        Staff see the organization's requests because they are the ones who answer for it.
        Everyone else sees the ones they raised — a support thread can contain anything its
        author chose to type, and there is no reason for a colleague to read it.
        """
        stmt = select(SupportRequest).where(SupportRequest.org_id == actor.org_id)
        if actor.role not in (UserRole.ADMIN, UserRole.TECHNICIAN):
            stmt = stmt.where(SupportRequest.created_by_user_id == actor.id)
        if status is not None:
            stmt = stmt.where(SupportRequest.status == status)
        stmt = stmt.order_by(SupportRequest.last_reply_at.desc().nullslast())
        return list((await self.session.execute(stmt)).scalars().all())

    async def get(
        self, *, actor: User, request_id: uuid.UUID, operator: bool = False
    ) -> SupportRequest:
        return await self._get_for(actor, request_id, operator=operator)

    async def org_name(self, org_id: uuid.UUID) -> str | None:
        return (await self.session.execute(
            select(Organization.name).where(Organization.id == org_id)
        )).scalar_one_or_none()

    async def author_emails(self, messages: list[SupportRequestMessage]) -> dict:
        """Resolve every message author in one query rather than one per message."""
        ids = {m.author_user_id for m in messages if m.author_user_id}
        if not ids:
            return {}
        return dict((await self.session.execute(
            select(User.id, User.email).where(User.id.in_(ids))
        )).all())

    async def messages(
        self, *, actor: User, request_id: uuid.UUID, operator: bool = False
    ) -> list[SupportRequestMessage]:
        await self._get_for(actor, request_id, operator=operator)
        return list((await self.session.execute(
            select(SupportRequestMessage)
            .where(SupportRequestMessage.request_id == request_id)
            .order_by(SupportRequestMessage.created_at.asc())
        )).scalars().all())

    # -- operator side --------------------------------------------------------

    async def queue(
        self, *, status: SupportRequestStatus | None = None, org_id: uuid.UUID | None = None,
        limit: int = 200,
    ) -> tuple[list[SupportRequest], dict[str, int], dict[str, str]]:
        """Every customer's requests, ours-first.

        Ordering is by whose turn it is rather than by age: a three-week-old thread waiting
        on the customer is not the oldest thing we owe anybody.
        """
        stmt: Select = select(SupportRequest)
        if status is not None:
            stmt = stmt.where(SupportRequest.status == status)
        if org_id is not None:
            stmt = stmt.where(SupportRequest.org_id == org_id)

        ours = case(
            (SupportRequest.status.in_(
                (SupportRequestStatus.OPEN, SupportRequestStatus.IN_PROGRESS)
            ), 0),
            else_=1,
        )
        priority_rank = case(
            (SupportRequest.priority == SupportRequestPriority.URGENT, 0),
            (SupportRequest.priority == SupportRequestPriority.HIGH, 1),
            (SupportRequest.priority == SupportRequestPriority.NORMAL, 2),
            else_=3,
        )
        rows = list((await self.session.execute(
            stmt.order_by(ours, priority_rank, SupportRequest.last_reply_at.asc().nullsfirst())
            .limit(limit)
        )).scalars().all())

        counts = dict((await self.session.execute(
            select(SupportRequest.status, func.count()).group_by(SupportRequest.status)
        )).all())
        org_names = dict((await self.session.execute(
            select(Organization.id, Organization.name)
        )).all())
        return (
            rows,
            {getattr(s, "value", s): n for s, n in counts.items()},
            {str(i): n for i, n in org_names.items()},
        )

    async def update(
        self, *, actor: User, request_id: uuid.UUID,
        status: SupportRequestStatus | None = None,
        priority: SupportRequestPriority | None = None,
    ) -> SupportRequest:
        request = await self._get_for(actor, request_id, operator=True)
        changes: dict[str, str] = {}

        if status is not None and status != request.status:
            request.status = status
            changes["status"] = status.value
            request.resolved_at = (
                utcnow() if status is SupportRequestStatus.RESOLVED else None
            )
            if status is SupportRequestStatus.RESOLVED:
                await NotificationService(self.session).notify(
                    org_id=request.org_id,
                    category=NotificationCategory.SYSTEM,
                    severity=NotificationSeverity.INFO,
                    title=f"Support request resolved — {request.reference}",
                    message=request.subject,
                    link="/help",
                )
        if priority is not None and priority != request.priority:
            request.priority = priority
            changes["priority"] = priority.value

        if changes:
            await self.audit.record(
                org_id=request.org_id, actor_id=actor.id,
                action="support_request.update",
                target_type="support_request", target_id=str(request.id),
                detail=changes,
            )
        await self.session.commit()
        return request

    # -- internals ------------------------------------------------------------

    async def _get_for(
        self, actor: User, request_id: uuid.UUID, *, operator: bool
    ) -> SupportRequest:
        request = await self.session.get(SupportRequest, request_id)
        if request is None:
            raise NotFoundError("Support request not found")
        if operator:
            # A platform operator answers across organizations by definition.
            return request
        if request.org_id != actor.org_id:
            raise NotFoundError("Support request not found")
        if (
            actor.role not in (UserRole.ADMIN, UserRole.TECHNICIAN)
            and request.created_by_user_id != actor.id
        ):
            raise NotFoundError("Support request not found")
        return request

    async def _unique_reference(self) -> str:
        for _ in range(5):
            candidate = _reference()
            exists = (await self.session.execute(
                select(SupportRequest.id).where(SupportRequest.reference == candidate)
            )).first()
            if exists is None:
                return candidate
        # Six hex characters colliding five times running means something is wrong with the
        # randomness, not with luck — falling back to a longer reference is safer than
        # looping forever.
        return f"SUP-{uuid.uuid4().hex[:12].upper()}"

    async def _diagnostics(self, org_id: uuid.UUID) -> dict:
        """The state of their world, as it stood when they asked.

        Aggregates only. A support ticket does not need hostnames or usernames to be
        actionable, and shipping them to the operator by default would put a customer's
        device inventory into a queue that exists for a different purpose.
        """
        now = utcnow()
        org = await self.session.get(Organization, org_id)

        total, online = (await self.session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(case(
                    (Device.last_seen_at >= now - ONLINE_THRESHOLD, 1), else_=0
                )), 0),
            ).where(Device.org_id == org_id)
        )).one()

        versions = dict((await self.session.execute(
            select(Device.agent_version, func.count())
            .where(Device.org_id == org_id)
            .group_by(Device.agent_version)
            .order_by(func.count().desc())
            .limit(6)
        )).all())

        rem_total, rem_failed = (await self.session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(case(
                    (RemediationTask.status == RemediationStatus.FAILED, 1), else_=0
                )), 0),
            ).where(RemediationTask.org_id == org_id)
        )).one()

        return {
            "captured_at": now.isoformat(),
            "plan": org.plan if org else None,
            "subscription_status": org.subscription_status.value if org else None,
            "licenses": org.license_count if org else 0,
            "devices_total": total,
            "devices_online": int(online),
            "devices_offline": total - int(online),
            "agent_versions": versions,
            "remediations_total": rem_total,
            "remediations_failed": int(rem_failed),
        }
