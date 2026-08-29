"""Lead capture — the one path in this service that must never lose data.

Everything else here is a convenience. If scoring is down the lead is unscored; if
Telegram is unconfigured nobody gets a ping; if Bigin's token expired the CRM is stale.
All recoverable. A dropped intake is not: the prospect saw a success message, believes
they made contact, and there is no record anywhere that they did.

So the ordering in `capture` is deliberate and worth preserving: persist and commit
first, then do everything that can fail.
"""
import asyncio
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email_domains import email_domain, is_free_email_domain
from app.models.lead import Lead, LeadStatus, LeadSubmission
from app.repositories.leads import LeadRepository
from app.schemas.lead import LeadIntake
from app.services.bigin import BiginClient
from app.services.dispatch import LeadDispatcher
from app.services.email import EmailService
from app.services.exceptions import NotConfiguredError, NotFoundError
from app.services.scoring import LeadScorer, score_rules
from app.services.telegram import TelegramNotifier

logger = logging.getLogger("astra.mkt.leads")


async def _false() -> bool:
    """A coroutine that is already False, so the gather below stays one shape."""
    return False


class LeadCapture:
    """What `capture` produced, for the caller to respond and dispatch with."""

    def __init__(self, lead: Lead, submission: LeadSubmission, is_new_lead: bool) -> None:
        self.lead = lead
        self.submission = submission
        self.is_new_lead = is_new_lead


class LeadService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = LeadRepository(session)

    async def capture(self, payload: LeadIntake) -> LeadCapture:
        """Store a form fill, creating or updating the person behind it.

        Commits before returning. The caller then dispatches downstream work outside this
        transaction, so a slow or dead n8n cannot hold a database transaction open — or,
        worse, roll back a lead that was already promised to the visitor.
        """
        email = payload.email.strip().lower()

        lead = await self.repo.get_by_email(email)
        is_new_lead = lead is None

        if lead is None:
            lead = Lead(
                email=email,
                name=payload.name,
                company=payload.company,
                phone=payload.phone,
                email_domain=email_domain(email) or None,
                is_free_email=is_free_email_domain(email),
            )
            self._record_consent(lead, payload)
            await self.repo.add(lead)
        else:
            # A returning prospect usually knows more about themselves than they did the
            # first time — they gave a company name on the demo request having left it
            # blank on the checklist download. Fill gaps, never overwrite: an existing
            # value may have been corrected by a human in the CRM, and a later form fill
            # is not evidence enough to undo that.
            lead.name = lead.name or payload.name
            lead.company = lead.company or payload.company
            lead.phone = lead.phone or payload.phone
            # Re-engaging is not the same as re-consenting, but a fresh submission with a
            # consent statement does renew it — and it un-does nothing if they opted out.
            if lead.unsubscribed_at is None:
                self._record_consent(lead, payload)

        submission = LeadSubmission(
            lead_id=lead.id,
            source=payload.source,
            interest=payload.interest,
            message=payload.message,
            landing_page=payload.landing_page,
            referrer=payload.referrer,
            utm_source=payload.utm_source,
            utm_medium=payload.utm_medium,
            utm_campaign=payload.utm_campaign,
            utm_content=payload.utm_content,
            utm_term=payload.utm_term,
        )

        try:
            await self.repo.add_submission(submission)
            # Score before the commit, so a lead is never briefly visible as UNSCORED and
            # a human never sees a row without a tier. The rules pass is pure Python —
            # no network, no key — which is exactly why it can live in the request path.
            # The model pass runs later, from the automation, via `rescore`.
            await self._apply_rules_score(lead)
            await self.session.commit()
        except IntegrityError:
            # Two forms submitted within milliseconds of each other by the same new
            # address — rare, but it is exactly the shape of a double-click on a slow
            # connection, and the unique index on email will reject the second insert.
            # The first one won; re-read it and attach this submission to it, so the
            # visitor's second click is recorded rather than erroring.
            await self.session.rollback()
            logger.info("lead insert raced on %s; attaching to the existing row", email)
            existing = await self.repo.get_by_email(email)
            if existing is None:
                raise
            submission = LeadSubmission(
                lead_id=existing.id,
                source=payload.source,
                interest=payload.interest,
                message=payload.message,
                landing_page=payload.landing_page,
                referrer=payload.referrer,
                utm_source=payload.utm_source,
                utm_medium=payload.utm_medium,
                utm_campaign=payload.utm_campaign,
                utm_content=payload.utm_content,
                utm_term=payload.utm_term,
            )
            await self.repo.add_submission(submission)
            await self._apply_rules_score(existing)
            await self.session.commit()
            return LeadCapture(existing, submission, is_new_lead=False)

        logger.info(
            "lead captured id=%s new=%s source=%s campaign=%s",
            lead.id, is_new_lead, payload.source, payload.utm_campaign or "-",
        )
        return LeadCapture(lead, submission, is_new_lead)

    async def _apply_rules_score(self, lead: Lead) -> None:
        """Set score, tier and reason from the deterministic rubric.

        Re-reads the lead's submissions rather than trusting the one just added: a
        returning prospect's earlier messages are part of the evidence, and the rubric
        rewards a fleet size mentioned on the first visit even when the second says only
        "following up".
        """
        stored = await self.repo.get_with_submissions(lead.id)
        submissions = list(stored.submissions) if stored else []

        result = score_rules(lead, submissions)
        lead.score = result.score
        lead.tier = result.tier
        lead.score_reason = result.summary
        lead.scored_at = datetime.now(UTC)
        if result.disqualified:
            lead.status = LeadStatus.DISQUALIFIED

    async def rescore(self, lead_id: uuid.UUID) -> Lead:
        """Re-run scoring including the model pass. Called by the automation, not inline.

        Deliberately out of the request path: the model call takes about a second, and a
        visitor's form submit should not wait on it. If the key is unset this collapses to
        the rules score, which is the same answer capture already stored — so calling it
        is always safe and never required.
        """
        lead = await self.repo.get_with_submissions(lead_id)
        if lead is None:
            raise NotFoundError(f"Lead {lead_id} not found")

        result = await LeadScorer().score(lead, list(lead.submissions))
        lead.score = result.score
        lead.tier = result.tier
        lead.score_reason = result.summary
        lead.scored_at = datetime.now(UTC)
        # Only ever moves a lead INTO disqualified, never out of one a human set. A model
        # that can un-disqualify would quietly undo a considered human decision.
        if result.disqualified and lead.status == LeadStatus.NEW:
            lead.status = LeadStatus.DISQUALIFIED

        await self.session.commit()
        logger.info(
            "lead rescored id=%s score=%s tier=%s model=%s",
            lead.id, lead.score, lead.tier.value, LeadScorer().model_enabled,
        )
        return lead

    async def fan_out(self, lead: Lead, submission: LeadSubmission) -> None:
        """Acknowledge the prospect, alert the team, and hand the lead to the automation.

        All three at once. They are independent best-effort side effects with no ordering
        between them, and running them in sequence cost the visitor the sum rather than
        the maximum — measured, that was 4.2 s instead of 2.9 s, and a cold start on top
        pushed intake past contact.php's 6 s timeout. Concurrent, the wall clock is
        whichever is slowest (SMTP, at about two seconds).

        Three separate outcomes, tracked separately: `acknowledged_at` is when the
        prospect was answered, `notified_at` is when a human was told, `dispatched_at` is
        when the automation took it. Any one can fail without the others, and a null on a
        lead older than a minute is a broken pipeline worth alerting on rather than a
        mystery.

        Inline rather than a FastAPI background task on purpose: Cloud Run throttles CPU
        outside the request by default, so work scheduled after the response is starved
        and may never run — the visitor would get a fast form and no email. Nothing here
        can raise.
        """
        dispatcher = LeadDispatcher()
        # The dispatch payload needs the lead's submissions, and loading them inside the
        # gather would serialise a database round trip against the network calls.
        stored = await self.repo.get_with_submissions(lead.id) if dispatcher.enabled else None

        results = await asyncio.gather(
            EmailService().send_acknowledgement(lead),
            TelegramNotifier().send_lead_alert(lead, submission),
            dispatcher.dispatch(stored or lead, submission) if dispatcher.enabled
            else _false(),
            return_exceptions=True,
        )
        acknowledged, notified, dispatched = (r is True for r in results)

        now = datetime.now(UTC)
        if acknowledged:
            lead.acknowledged_at = now
        if notified:
            lead.notified_at = now
        if dispatcher.enabled:
            submission.dispatch_attempts += 1
            if dispatched:
                submission.dispatched_at = now
        # One commit for all three, rather than one per outcome.
        await self.session.commit()

        logger.info("lead %s fanned out: acknowledged=%s alerted=%s dispatched=%s",
                    lead.id, acknowledged, notified, dispatched)

    async def sync_to_crm(self, lead_id: uuid.UUID) -> Lead:
        """Push the lead to Bigin as a Contact plus a Pipeline record.

        Deliberately out of the intake path. Two API round trips is one to two seconds,
        and nothing depends on the CRM being current within the minute: the lead is
        already committed here and the founder has already been alerted. What would be
        harmed by putting it inline is the visitor's form.

        Idempotent on the contact (Bigin upserts on email) and guarded on the pipeline
        record, so a retry after a partial failure does not create a second deal.
        """
        lead = await self.repo.get_with_submissions(lead_id)
        if lead is None:
            raise NotFoundError(f"Lead {lead_id} not found")

        client = BiginClient()
        if not client.enabled:
            raise NotConfiguredError("Bigin is not configured")

        latest = lead.submissions[-1] if lead.submissions else None
        contact_id = await client.upsert_contact(lead)

        if not lead.crm_record_id:
            sub_pipelines = await client.sub_pipeline_names()
            if not sub_pipelines:
                raise NotConfiguredError("Bigin has no sub-pipeline configured")
            lead.crm_record_id = await client.create_pipeline_record(
                lead, latest, contact_id, sub_pipeline=sub_pipelines[0]
            )
        else:
            # The record exists; only move it. Never recreate — a human may have worked
            # this deal, and a second one would split the history in two.
            await client.update_stage(lead.crm_record_id, lead.status)

        lead.crm_provider = "bigin"
        lead.crm_synced_at = datetime.now(UTC)
        await self.session.commit()

        logger.info("lead %s synced to bigin: contact=%s record=%s",
                    lead.id, contact_id, lead.crm_record_id)
        return lead

    async def sync_pending(self, *, limit: int = 25) -> dict[str, int]:
        """Sync every lead that has never reached the CRM.

        The safety net behind the automation. One failure must not stop the batch — a
        single lead with an address Bigin rejects would otherwise block every lead behind
        it, which is exactly how a backlog becomes permanent.
        """
        pending = await self.repo.list_unsynced(limit=limit)
        synced = failed = 0
        for lead in pending:
            try:
                await self.sync_to_crm(lead.id)
                synced += 1
            except Exception as exc:  # noqa: BLE001 — one bad lead must not stop the rest
                failed += 1
                logger.warning("crm sync failed for lead %s: %s", lead.id, exc)
        return {"pending": len(pending), "synced": synced, "failed": failed}

    async def mark_dispatched(self, submission: LeadSubmission) -> None:
        submission.dispatched_at = datetime.now(UTC)
        submission.dispatch_attempts += 1
        await self.session.commit()

    async def mark_dispatch_failed(self, submission: LeadSubmission) -> None:
        """Count the attempt without setting dispatched_at, so the sweeper retries it."""
        submission.dispatch_attempts += 1
        await self.session.commit()

    @staticmethod
    def _record_consent(lead: Lead, payload: LeadIntake) -> None:
        """Write down what they agreed to and when.

        The DPDP Act wants consent to be demonstrable, which means storing the wording the
        person actually saw, not a boolean. When the form carries no consent text we still
        record the source — a contact form is consent to be *replied to*, and that
        distinction is what `Lead.is_contactable` reads before any marketing send.
        """
        lead.consent_source = payload.consent_text or f"form:{payload.source}"
        lead.consent_at = datetime.now(UTC)
