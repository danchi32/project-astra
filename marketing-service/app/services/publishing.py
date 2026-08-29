"""The only path from approved copy to a live post.

Everything else in this service can be retried, corrected, or deleted. This cannot: once
LinkedIn returns 201 the words are public, and no amount of state management takes them
back. So the order of operations here is the design, and it is deliberately boring.

**The gate runs first, and it runs on the same object that gets published.** Not a status
check — `ContentService.assert_publishable`, the one the regression tests are written
against. There is no second implementation of "is this allowed out" anywhere in the
codebase, because two implementations means one of them is eventually wrong.

**What goes out is the APPROVED version, fetched by id — never "the current one".** The
gate already refuses when those differ, so this is belt and braces; but the belt is the
thing that decides what words leave the building, and it should name them explicitly
rather than infer them. A future change that moves `current_version_id` cannot quietly
redirect this.

**A live post is recorded even when recording is refused.** The one genuinely nasty case:
the API call succeeds, and between the gate and the write something changes such that
`mark_published` refuses. The post is live. Swallowing that leaves a published post the
database thinks is a draft, which is the worst state this system can be in — so it is
recorded as an event with the URL, logged at ERROR, and raised as its own exception type
that says exactly what happened.

**Publishing twice is refused before it is attempted.** A crash between the API call and
the write would otherwise be repaired by a retry that posts a second copy.
"""
import logging
import uuid

from app.models.content import ContentChannel, ContentEventType, ContentItem, ContentVersion
from app.services.content import ContentService, PublishRefused
from app.services.exceptions import NotFoundError, ValidationError
from app.services.publishers.base import PublisherError, PublishResult
from app.services.publishers.linkedin import LinkedInPublisher

logger = logging.getLogger("astra.mkt.publishing")


class PublishedButNotRecorded(Exception):
    """The post is live and the database does not know.

    Its own type because it needs its own response: nobody should retry, and somebody has
    to reconcile by hand. The message carries the URL.
    """


#: Channel -> publisher. A channel absent from here cannot be published by this service,
#: which is the correct default: a new channel should require someone to write and test a
#: publisher for it, not inherit one by accident.
_PUBLISHERS = {
    ContentChannel.LINKEDIN: LinkedInPublisher,
}


class PublishingService:
    def __init__(self, session) -> None:
        self.session = session
        self.content = ContentService(session)

    def publisher_for(self, channel: ContentChannel):
        publisher_class = _PUBLISHERS.get(channel)
        if publisher_class is None:
            raise ValidationError(
                f"Nothing in this service publishes to {channel.value} yet. "
                "Record it with POST /content/{id}/published after posting by hand."
            )
        return publisher_class()

    async def approved_version(self, item: ContentItem) -> ContentVersion:
        """The words a human said yes to, by id.

        `assert_publishable` has already refused if this is not also the current version.
        Fetching by `approved_version_id` anyway means the thing that decides what gets
        transmitted is the same field that records the approval.
        """
        if item.approved_version_id is None:
            raise PublishRefused("Nothing has been approved on this item.")

        version = next(
            (v for v in item.versions if v.id == item.approved_version_id), None
        )
        if version is None:
            raise PublishRefused(
                "The approved version is missing from the history; refusing to guess "
                "which words were meant."
            )
        return version

    async def preview(self, item_id: uuid.UUID) -> dict:
        """Exactly what would be transmitted, without transmitting it.

        Worth having for a system whose failure mode is public: the escaping and hashtag
        templating make the wire format differ visibly from the approved text, and that
        difference should be inspectable before it is irreversible rather than after.
        """
        item = await self.content.get(item_id)
        publisher = self.publisher_for(item.channel)
        version = await self.approved_version(item)

        rendered = publisher.render(version)
        return {
            "channel": item.channel.value,
            "version_number": version.version_number,
            "approved_by": item.approved_by,
            "characters": len(rendered),
            "rendered": rendered,
            "publisher_configured": publisher.enabled,
        }

    async def publish(self, item_id: uuid.UUID, *, actor: str) -> PublishResult:
        item = await self.content.get(item_id)

        # 1. Already out? Refuse before touching the network. A retry after a crash must
        #    not put a second copy on the page.
        if item.published_ref:
            raise ValidationError(
                f"Already published as {item.published_ref} "
                f"({item.published_url or 'no URL recorded'})."
            )

        # 2. The gate. Same call the regression tests are written against.
        self.content.assert_publishable(item)

        publisher = self.publisher_for(item.channel)
        version = await self.approved_version(item)

        # 3. The irreversible part.
        result = await publisher.publish(version)

        # 4. Record it. From here the post exists whatever happens.
        try:
            await self.content.mark_published(
                item_id, actor=actor, url=result.url, ref=result.ref
            )
        except (PublishRefused, ValidationError) as exc:
            logger.error(
                "PUBLISHED BUT NOT RECORDED: %s is live at %s and the database refused to "
                "record it (%s). Reconcile by hand.",
                item_id, result.url, exc,
            )
            await self.content.record_event(
                item, ContentEventType.PUBLISH_REFUSED, actor,
                version_id=version.id,
                note=f"Post is LIVE at {result.url} ({result.ref}) but recording was "
                     f"refused: {exc}",
            )
            raise PublishedButNotRecorded(
                f"The post is live at {result.url}, but recording it was refused: {exc}. "
                "Do not retry — that would post it a second time."
            ) from exc

        logger.info("published %s to %s as %s", item_id, item.channel.value, result.ref)
        return result

    async def publish_due(self, *, actor: str = "scheduler") -> list[dict]:
        """Everything scheduled and due.

        Being due is not permission: each one still goes through `publish` above, so an
        item whose approval was invalidated after it was scheduled is refused rather than
        published because a timer fired. Failures are collected, not raised — one bad item
        must not stop the rest of the queue.
        """
        outcomes: list[dict] = []
        for item in await self.content.due_for_publishing():
            try:
                result = await self.publish(item.id, actor=actor)
                outcomes.append({"id": str(item.id), "status": "published",
                                 "url": result.url})
            except (PublishRefused, ValidationError, PublisherError,
                    PublishedButNotRecorded, NotFoundError) as exc:
                logger.warning("scheduled publish of %s did not go out: %s", item.id, exc)
                outcomes.append({"id": str(item.id), "status": "skipped",
                                 "reason": str(exc)})
        return outcomes
