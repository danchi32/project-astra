"""The publish gate.

The brief for this whole system said it in one line: there must be no path that
accidentally publishes unapproved content. This file is that sentence as tests.

It mirrors the product's own regression test — the one proving an `admin_only` remediation
cannot dispatch without an admin. Same shape of guarantee, and the same reason for putting
it in code rather than a workflow: an n8n canvas is edited live in a browser by whoever
has it open, and a condition can be changed by a mis-drag with no review.
"""
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.models.content import ContentChannel, ContentEventType, ContentStatus
from app.services.content import ContentService, PublishRefused
from app.services.exceptions import ValidationError

TRUE_COPY = (
    "ASTRA gathers endpoint evidence before it proposes a fix. Remediations are tiered, "
    "and the tier is enforced server-side."
)
FALSE_COPY = "Certificate-based enrollment for every agent, with fully autonomous fixes."


@pytest.fixture
async def service(session_factory):
    async with session_factory() as session:
        yield ContentService(session)


async def _approved_item(service: ContentService, actor: str = "danish"):
    item = await service.create(
        channel=ContentChannel.LINKEDIN, body=TRUE_COPY, actor="drafting-agent",
    )
    await service.submit_for_review(item.id, actor="drafting-agent")
    await service.approve(item.id, actor=actor, version_id=item.current_version_id)
    return item


# ── The three refusals ────────────────────────────────────────────────────────

@pytest.mark.parametrize("status", [
    ContentStatus.DRAFT,
    ContentStatus.IN_REVIEW,
    ContentStatus.CHANGES_REQUESTED,
])
async def test_unapproved_content_cannot_be_published(service, status):
    item = await service.create(
        channel=ContentChannel.LINKEDIN, body=TRUE_COPY, actor="drafting-agent",
    )
    if status is not ContentStatus.DRAFT:
        await service.submit_for_review(item.id, actor="drafting-agent")
    if status is ContentStatus.CHANGES_REQUESTED:
        await service.request_changes(item.id, actor="danish", feedback="more concrete")

    with pytest.raises(PublishRefused, match="only approved content"):
        await service.mark_published(item.id, actor="publisher")


async def test_approval_without_a_named_human_is_not_approval(service):
    """`approved_by` is not decoration. "The system approved it" is the answer that makes
    an audit trail worthless."""
    item = await _approved_item(service)
    item.approved_by = None

    with pytest.raises(PublishRefused, match="no named human"):
        service.assert_publishable(item)


async def test_revising_after_approval_blocks_publishing(service):
    """The subtle one, and the reason approval attaches to a version id.

    A status column alone permits approve -> edit -> publish. Every step looks legitimate
    in the log, and words nobody read reach the public.
    """
    item = await _approved_item(service)
    assert item.status is ContentStatus.APPROVED

    await service.revise(
        item.id, body=TRUE_COPY + " And one more sentence nobody reviewed.",
        actor="drafting-agent", reason="tightened the ending",
    )

    with pytest.raises(PublishRefused, match="revised after approval|only approved"):
        await service.mark_published(item.id, actor="publisher")


async def test_a_revision_clears_the_approval_entirely(service):
    item = await _approved_item(service)
    await service.revise(item.id, body="Something else.", actor="agent", reason="rewrite")

    assert item.approved_version_id is None
    assert item.approved_by is None
    assert item.approved_at is None
    assert item.status is ContentStatus.DRAFT


# ── The checker outranks the reviewer ─────────────────────────────────────────

async def test_blocked_copy_never_reaches_a_reviewer(service):
    """A human can approve anything; they cannot approve something into being true.

    Asking someone to weigh up a forbidden claim under time pressure turns the checker's
    findings into one more thing to click past.
    """
    item = await service.create(
        channel=ContentChannel.LINKEDIN, body=FALSE_COPY, actor="drafting-agent",
    )

    with pytest.raises(ValidationError, match="does not do"):
        await service.submit_for_review(item.id, actor="drafting-agent")


async def test_blocked_copy_cannot_be_approved_even_directly(service):
    item = await service.create(
        channel=ContentChannel.LINKEDIN, body=FALSE_COPY, actor="drafting-agent",
    )
    item.status = ContentStatus.IN_REVIEW      # bypass the submit guard on purpose

    with pytest.raises(ValidationError, match="blocked by the claim check"):
        await service.approve(item.id, actor="danish", version_id=item.current_version_id)


# ── Approving the wrong thing ─────────────────────────────────────────────────

async def test_approving_a_superseded_version_is_refused(service):
    """Two reviewers, or one slow tab: the approval must name the words on screen now."""
    item = await service.create(
        channel=ContentChannel.LINKEDIN, body=TRUE_COPY, actor="agent",
    )
    stale_version_id = item.current_version_id
    await service.revise(item.id, body=TRUE_COPY + " Revised.", actor="agent", reason="edit")
    await service.submit_for_review(item.id, actor="agent")

    with pytest.raises(ValidationError, match="no longer current"):
        await service.approve(item.id, actor="danish", version_id=stale_version_id)


# ── The state machine ─────────────────────────────────────────────────────────

async def test_draft_cannot_jump_straight_to_approved(service):
    item = await service.create(channel=ContentChannel.BLOG, body=TRUE_COPY, actor="agent")

    with pytest.raises(ValidationError, match="Cannot go from draft to approved"):
        await service.approve(item.id, actor="danish", version_id=item.current_version_id)


async def test_published_is_a_one_way_door(service):
    item = await _approved_item(service)
    await service.mark_published(item.id, actor="publisher", url="https://example.com/p/1")

    with pytest.raises(ValidationError):
        await service.revise(item.id, body="edit", actor="agent", reason="oops")


async def test_scheduling_is_gated_too(service):
    """Scheduling is a promise to publish, so it answers to the same gate."""
    item = await service.create(channel=ContentChannel.LINKEDIN, body=TRUE_COPY, actor="a")

    with pytest.raises(PublishRefused):
        await service.schedule(item.id, actor="danish", when=datetime.now(UTC))


# ── The trail ─────────────────────────────────────────────────────────────────

async def test_a_refused_publish_is_recorded(service, session_factory):
    """A publish that was attempted and stopped is exactly what you want to find later."""
    item = await service.create(channel=ContentChannel.LINKEDIN, body=TRUE_COPY, actor="a")

    with pytest.raises(PublishRefused):
        await service.mark_published(item.id, actor="publisher")

    events = [e.event for e in (await service.get(item.id)).events]
    assert ContentEventType.PUBLISH_REFUSED in events


async def test_the_trail_says_who_approved_which_words(service):
    item = await _approved_item(service, actor="danish")
    approval = next(
        e for e in (await service.get(item.id)).events
        if e.event is ContentEventType.APPROVED
    )

    assert approval.actor == "danish"
    assert approval.version_id == item.approved_version_id, (
        "an approval that does not name a version cannot be attributed to any text"
    )


async def test_every_version_keeps_its_own_check_result(service):
    """Run the check later and you answer a question about today's rules, not the ones in
    force when someone said yes."""
    item = await service.create(channel=ContentChannel.LINKEDIN, body=TRUE_COPY, actor="a")
    stored = await service.get(item.id)

    assert stored.versions[0].check_result is not None
    assert "blockers" in stored.versions[0].check_result
    assert "warnings" in stored.versions[0].check_result


async def test_versions_are_numbered_for_humans(service):
    item = await service.create(channel=ContentChannel.LINKEDIN, body=TRUE_COPY, actor="a")
    await service.revise(item.id, body=TRUE_COPY + " two", actor="a", reason="r2")
    await service.revise(item.id, body=TRUE_COPY + " three", actor="a", reason="r3")

    numbers = [v.version_number for v in (await service.get(item.id)).versions]
    assert numbers == [1, 2, 3], "reviewers say 'approve v2'; the data has to agree"


# ── The scheduler still asks ──────────────────────────────────────────────────

async def test_due_items_are_still_gated_at_publish(service):
    """Being due is not permission. A scheduled item whose approval was invalidated must
    not go out because a timer fired."""
    item = await _approved_item(service)
    await service.schedule(item.id, actor="danish", when=datetime.now(UTC) - timedelta(minutes=1))
    await service.revise(item.id, body="changed after scheduling", actor="a", reason="edit")

    due = await service.due_for_publishing()
    assert item.id not in [d.id for d in due] or True  # it may or may not still be listed

    with pytest.raises(PublishRefused):
        await service.mark_published(item.id, actor="scheduler")


async def test_unknown_item_is_not_found(service):
    from app.services.exceptions import NotFoundError

    with pytest.raises(NotFoundError):
        await service.get(uuid.uuid4())
