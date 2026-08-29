"""Content lifecycle, and the gate that decides whether anything may be published.

This module exists so that the answer to "can this be published?" lives in code with a
test on it, rather than in an n8n node that anyone with the editor open can drag. The
product makes the same distinction about remediation: approval tiers are enforced in the
backend, never in a prompt. Same rule, different blast radius.

Three refusals, and each is a separate way the obvious implementation goes wrong:

1. Status is not APPROVED. The easy one.
2. Approved, but revised since. A status column alone allows approve → edit → publish,
   which puts words in front of the public that nobody read. Approval attaches to a
   version id; publishing checks it still matches.
3. The claim checker blocked the approved version. A human can approve anything; they
   cannot approve something into being true. If the checker found a forbidden claim, no
   amount of sign-off makes it publishable.
"""
import logging
import uuid
from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.content import (
    ContentChannel,
    ContentEvent,
    ContentEventType,
    ContentItem,
    ContentStatus,
    ContentVersion,
)
from app.services.claims import check_text
from app.services.exceptions import NotFoundError, ValidationError

logger = logging.getLogger("astra.mkt.content")


class PublishRefused(Exception):
    """The gate said no. Carries the reason, because a bare refusal is unactionable."""


#: Which statuses may move to which. Anything not listed here is refused, so a new status
#: cannot silently acquire a path to PUBLISHED by being added to the enum.
_ALLOWED: dict[ContentStatus, set[ContentStatus]] = {
    ContentStatus.DRAFT: {ContentStatus.IN_REVIEW, ContentStatus.ARCHIVED},
    ContentStatus.IN_REVIEW: {
        ContentStatus.APPROVED, ContentStatus.CHANGES_REQUESTED, ContentStatus.ARCHIVED,
    },
    ContentStatus.CHANGES_REQUESTED: {ContentStatus.IN_REVIEW, ContentStatus.ARCHIVED},
    ContentStatus.APPROVED: {
        ContentStatus.SCHEDULED, ContentStatus.PUBLISHED,
        # A revision after approval drops back to DRAFT and clears the approval. It has to
        # be re-reviewed: the words changed.
        ContentStatus.DRAFT, ContentStatus.ARCHIVED,
    },
    ContentStatus.SCHEDULED: {
        ContentStatus.PUBLISHED, ContentStatus.DRAFT, ContentStatus.ARCHIVED,
    },
    # Nothing leaves PUBLISHED. Taking a post down is a platform action and a new record,
    # not a state change that quietly rewrites what happened.
    ContentStatus.PUBLISHED: set(),
    ContentStatus.ARCHIVED: {ContentStatus.DRAFT},
}


class ContentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Reading ────────────────────────────────────────────────────────────────

    async def get(self, item_id: uuid.UUID) -> ContentItem:
        """Load an item with its versions and events, refreshed from the database.

        A plain `session.get()` returns whatever is in the identity map, and versions are
        added as their own rows rather than through `item.versions`, so the in-memory
        collection on a just-created item is empty and stale. `populate_existing` forces
        the refresh; without it, reading the history of an item this session created
        returns nothing and looks like data loss.
        """
        stmt = (
            select(ContentItem)
            .where(ContentItem.id == item_id)
            .options(selectinload(ContentItem.versions), selectinload(ContentItem.events))
            .execution_options(populate_existing=True)
        )
        item = (await self.session.execute(stmt)).scalars().first()
        if item is None:
            raise NotFoundError(f"Content {item_id} not found")
        return item

    async def current_version(self, item: ContentItem) -> ContentVersion | None:
        if item.current_version_id is None:
            return None
        return await self.session.get(ContentVersion, item.current_version_id)

    # ── Writing ────────────────────────────────────────────────────────────────

    async def create(
        self, *, channel: ContentChannel, body: str, actor: str,
        campaign: str | None = None, brief: str | None = None,
        headline: str | None = None, hashtags: str | None = None,
        cta: str | None = None, media_url: str | None = None,
        authored_by: str | None = None,
    ) -> ContentItem:
        """Create an item with its first version, checked."""
        item = ContentItem(channel=channel, campaign=campaign, brief=brief)
        self.session.add(item)
        await self.session.flush()

        version = await self._add_version(
            item, body=body, headline=headline, hashtags=hashtags, cta=cta,
            media_url=media_url, authored_by=authored_by, revision_reason=None,
        )
        self._record(item, ContentEventType.CREATED, actor, version_id=version.id)
        await self.session.commit()
        return item

    async def revise(
        self, item_id: uuid.UUID, *, body: str, actor: str, reason: str,
        headline: str | None = None, hashtags: str | None = None,
        cta: str | None = None, media_url: str | None = None,
        authored_by: str | None = None,
    ) -> ContentVersion:
        """Add a new version, and drop any approval that was riding on the old one.

        The clearing is not tidiness. Without it, approve → revise → publish sends words
        no human has read, and every part of that sequence looks legitimate in the log.
        """
        item = await self.get(item_id)
        if item.status is ContentStatus.PUBLISHED:
            raise ValidationError("Published content cannot be revised; create a new item.")

        version = await self._add_version(
            item, body=body, headline=headline, hashtags=hashtags, cta=cta,
            media_url=media_url, authored_by=authored_by, revision_reason=reason,
        )

        if item.approved_version_id is not None:
            logger.info(
                "content %s revised after approval; approval of %s no longer applies",
                item.id, item.approved_version_id,
            )
            item.approved_version_id = None
            item.approved_by = None
            item.approved_at = None
            item.status = ContentStatus.DRAFT

        self._record(item, ContentEventType.REVISED, actor, version_id=version.id, note=reason)
        await self.session.commit()
        return version

    async def submit_for_review(self, item_id: uuid.UUID, *, actor: str) -> ContentItem:
        """Send it to a human — but not if the checker refused it.

        A blocked draft never reaches a reviewer. There is no version of "the product does
        not do this" worth putting in front of someone to weigh up at speed, and asking
        them to means the checker's findings become one more thing to click past.
        """
        item = await self.get(item_id)
        version = await self.current_version(item)
        if version is None:
            raise ValidationError("Nothing to review: the item has no version.")
        if version.blocked:
            blockers = version.check_result.get("blockers", [])
            raise ValidationError(
                "This draft states something the product does not do: "
                + "; ".join(b.get("rule", "?") for b in blockers)
                + ". Revise it rather than asking for approval."
            )

        self._transition(item, ContentStatus.IN_REVIEW)
        self._record(item, ContentEventType.SUBMITTED, actor, version_id=version.id)
        await self.session.commit()
        return item

    async def approve(
        self, item_id: uuid.UUID, *, actor: str, version_id: uuid.UUID
    ) -> ContentItem:
        """Approve one specific version.

        The caller must name the version. Approving "the item" is how a reviewer ends up
        having endorsed something that arrived after they looked — the id is what makes an
        approval mean anything later.
        """
        item = await self.get(item_id)
        if version_id != item.current_version_id:
            raise ValidationError(
                "That version is no longer current — the content changed after it was "
                "sent for review. Look at the new one."
            )
        version = await self.current_version(item)
        if version is not None and version.blocked:
            raise ValidationError(
                "This version is blocked by the claim check and cannot be approved."
            )

        self._transition(item, ContentStatus.APPROVED)
        item.approved_version_id = version_id
        item.approved_by = actor
        item.approved_at = datetime.now(UTC)
        self._record(item, ContentEventType.APPROVED, actor, version_id=version_id)
        await self.session.commit()
        return item

    async def request_changes(
        self, item_id: uuid.UUID, *, actor: str, feedback: str
    ) -> ContentItem:
        item = await self.get(item_id)
        self._transition(item, ContentStatus.CHANGES_REQUESTED)
        self._record(
            item, ContentEventType.CHANGES_REQUESTED, actor,
            version_id=item.current_version_id, note=feedback,
        )
        await self.session.commit()
        return item

    async def schedule(self, item_id: uuid.UUID, *, actor: str, when: datetime) -> ContentItem:
        item = await self.get(item_id)
        self.assert_publishable(item)          # scheduling is a promise to publish
        self._transition(item, ContentStatus.SCHEDULED)
        item.scheduled_for = when
        self._record(item, ContentEventType.SCHEDULED, actor,
                     version_id=item.approved_version_id, note=when.isoformat())
        await self.session.commit()
        return item

    # ── The gate ───────────────────────────────────────────────────────────────

    def assert_publishable(self, item: ContentItem) -> None:
        """Raise unless this may go out. The single place that decides.

        Called by `mark_published` and by `schedule`, and nothing publishes without going
        through one of those. Deliberately synchronous and dependency-free so it can be
        read in one sitting and tested without a database.
        """
        if item.status not in (ContentStatus.APPROVED, ContentStatus.SCHEDULED):
            raise PublishRefused(
                f"status is {item.status.value}; only approved content may be published"
            )
        if item.approved_version_id is None or not item.approved_by:
            raise PublishRefused("no named human has approved this")
        if not item.approval_is_current:
            raise PublishRefused(
                "the content was revised after approval; the approved version is not the "
                "current one"
            )

    async def mark_published(
        self, item_id: uuid.UUID, *, actor: str, url: str | None = None,
        ref: str | None = None,
    ) -> ContentItem:
        """Record that the approved version went out.

        The publisher calls the platform API and then calls this. The refusal is recorded
        as an event too: a publish that was attempted and stopped is exactly the thing
        worth being able to find afterwards.
        """
        item = await self.get(item_id)
        try:
            self.assert_publishable(item)
        except PublishRefused as exc:
            self._record(item, ContentEventType.PUBLISH_REFUSED, actor,
                         version_id=item.current_version_id, note=str(exc))
            await self.session.commit()
            logger.warning("refused to publish content %s: %s", item.id, exc)
            raise

        item.status = ContentStatus.PUBLISHED
        item.published_at = datetime.now(UTC)
        item.published_url = url
        item.published_ref = ref
        self._record(item, ContentEventType.PUBLISHED, actor,
                     version_id=item.approved_version_id, note=url)
        await self.session.commit()
        logger.info("content %s published (version %s) by %s",
                    item.id, item.approved_version_id, actor)
        return item

    async def due_for_publishing(self, *, now: datetime | None = None) -> list[ContentItem]:
        """Scheduled items whose time has come. Still gated at publish."""
        moment = now or datetime.now(UTC)
        stmt = (
            select(ContentItem)
            .where(ContentItem.status == ContentStatus.SCHEDULED)
            .where(ContentItem.scheduled_for.is_not(None))
            .where(ContentItem.scheduled_for <= moment)
            .order_by(ContentItem.scheduled_for)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    # ── Internals ──────────────────────────────────────────────────────────────

    async def _add_version(
        self, item: ContentItem, *, body: str, headline: str | None,
        hashtags: str | None, cta: str | None, media_url: str | None,
        authored_by: str | None, revision_reason: str | None,
    ) -> ContentVersion:
        next_number = (await self.session.execute(
            select(func.coalesce(func.max(ContentVersion.version_number), 0) + 1)
            .where(ContentVersion.content_item_id == item.id)
        )).scalar_one()

        # Checked at write time, and the verdict stored with the words. Running the check
        # later would answer a question about today's rules, not the ones in force when a
        # human said yes.
        checked = " ".join(filter(None, [headline, body, cta, hashtags]))
        result = check_text(checked)

        version = ContentVersion(
            content_item_id=item.id, version_number=next_number, body=body,
            headline=headline, hashtags=hashtags, cta=cta, media_url=media_url,
            authored_by=authored_by, revision_reason=revision_reason,
            check_result={
                "blockers": [asdict(f) for f in result.blockers],
                "warnings": [asdict(f) for f in result.warnings],
            },
        )
        self.session.add(version)
        await self.session.flush()

        item.current_version_id = version.id
        self._record(item, ContentEventType.CHECKED, "claim-checker", version_id=version.id,
                     note=f"{len(result.blockers)} blockers, {len(result.warnings)} warnings")
        return version

    def _transition(self, item: ContentItem, to: ContentStatus) -> None:
        if to not in _ALLOWED[item.status]:
            raise ValidationError(
                f"Cannot go from {item.status.value} to {to.value}."
            )
        item.status = to

    async def record_event(
        self, item: ContentItem, event: ContentEventType, actor: str,
        *, version_id: uuid.UUID | None = None, note: str | None = None,
    ) -> None:
        """Append to the trail from outside this service, and commit.

        Exists for one caller: the publisher, when a post went live and recording it was
        refused. That fact has to reach the history even though every normal write path
        has just declined — so it gets a door of its own rather than the publisher
        reaching into a private method.
        """
        self._record(item, event, actor, version_id=version_id, note=note)
        await self.session.commit()

    def _record(
        self, item: ContentItem, event: ContentEventType, actor: str,
        *, version_id: uuid.UUID | None = None, note: str | None = None,
    ) -> None:
        self.session.add(ContentEvent(
            content_item_id=item.id, version_id=version_id, event=event,
            actor=actor, note=note,
        ))
