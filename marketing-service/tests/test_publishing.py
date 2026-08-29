"""Publishing — the irreversible step.

Everything else this service does can be retried or corrected. Once LinkedIn returns 201
the words are public. So these tests are weighted towards the two things that cannot be
fixed afterwards: what actually goes out on the wire, and whether the gate can be got past.

No test here touches the network. `fake_linkedin` installs an httpx MockTransport and
records every request, which is also how the wire-format assertions get something real to
inspect rather than a re-implementation of the renderer.
"""
import json
import uuid

import httpx
import pytest
import pytest_asyncio

from app.core.config import get_settings
from app.models.content import ContentChannel, ContentEventType, ContentStatus
from app.services.content import ContentService, PublishRefused
from app.services.exceptions import ValidationError
from app.services.publishers import linkedin as li
from app.services.publishers.base import PublisherError
from app.services.publishing import PublishedButNotRecorded, PublishingService

TRUE_COPY = (
    "ASTRA gathers endpoint evidence before it proposes a fix. Remediations are tiered, "
    "and the tier is enforced server-side."
)
ORG_ID = "98765"
POST_URN = "urn:li:share:6844785523593134080"


class FakeLinkedIn:
    """Records requests; answers however the test tells it to."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.status = 201
        self.body = ""
        self.headers = {"x-restli-id": POST_URN}

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status, headers=self.headers, text=self.body)

    @property
    def payload(self) -> dict:
        return json.loads(self.requests[-1].content)

    @property
    def commentary(self) -> str:
        return self.payload["commentary"]


@pytest.fixture
def fake_linkedin(monkeypatch) -> FakeLinkedIn:
    fake = FakeLinkedIn()
    settings = get_settings()
    monkeypatch.setattr(settings, "linkedin_access_token", "test-token")
    monkeypatch.setattr(settings, "linkedin_organization_id", ORG_ID)

    real_client = httpx.AsyncClient

    def _client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(fake.handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(li.httpx, "AsyncClient", _client)
    return fake


@pytest_asyncio.fixture
async def publishing(session_factory):
    async with session_factory() as session:
        yield PublishingService(session)


async def _approved(publishing: PublishingService, *, body=TRUE_COPY, **kwargs):
    service: ContentService = publishing.content
    item = await service.create(
        channel=kwargs.pop("channel", ContentChannel.LINKEDIN),
        body=body, actor="drafting-agent", **kwargs,
    )
    await service.submit_for_review(item.id, actor="drafting-agent")
    await service.approve(item.id, actor="danish", version_id=item.current_version_id)
    return await service.get(item.id)


# ── The wire format ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("char", list("\\|{}@[]()<>#*_~"))
def test_every_reserved_character_is_escaped(char):
    """LinkedIn's docs are explicit: reserved characters must be escaped *even when they
    are not being used as markup*. Miss one and the post publishes mangled — LinkedIn
    accepts it, so nothing fails loudly."""
    assert li.escape_little(char) == "\\" + char


def test_backslashes_are_escaped_before_anything_else():
    """The ordering bug this design avoids.

    Escaping "(" and then "\\" would go back over the backslashes the first pass just
    added and double them. Doing it per character makes the order unrepresentable.
    """
    assert li.escape_little("\\(") == "\\\\\\("
    assert li.escape_little("C:\\Windows") == "C:\\\\Windows"


def test_ordinary_prose_survives_untouched():
    text = "Evidence before action. Tiered remediation, enforced server-side."
    assert li.escape_little(text) == text


def test_hashtags_become_templates_not_escaped_text():
    """The deliberate exception to escaping everything.

    A `\\#ITOps` renders as four visible characters that link to nothing. Escaping the
    whole post uniformly would have been simpler and would have silently cost every post
    its hashtags.
    """
    assert li.hashtag_template("#ITOps") == "{hashtag|\\#|ITOps}"
    assert li.hashtag_template("ITOps") == "{hashtag|\\#|ITOps}"


def test_a_malformed_hashtag_is_shown_not_dropped():
    """It should be visible in the post and get fixed, not silently swallowed."""
    assert li.hashtag_template("#not a tag") == "\\#not a tag"


async def test_the_rendered_post_carries_body_cta_and_tags(publishing, fake_linkedin):
    item = await _approved(publishing)
    await publishing.content.revise(
        item.id, body="Costs (a lot) less in snake_case.", cta="See how it works",
        hashtags="#ITOps #Automation", actor="agent", reason="add cta",
    )
    await publishing.content.submit_for_review(item.id, actor="agent")
    item = await publishing.content.get(item.id)
    await publishing.content.approve(item.id, actor="danish",
                                     version_id=item.current_version_id)

    await publishing.publish(item.id, actor="danish")

    body = fake_linkedin.commentary
    assert "Costs \\(a lot\\) less in snake\\_case." in body
    assert "See how it works" in body
    assert "{hashtag|\\#|ITOps} {hashtag|\\#|Automation}" in body


async def test_the_request_matches_what_linkedin_documents(publishing, fake_linkedin):
    item = await _approved(publishing)
    await publishing.publish(item.id, actor="danish")

    request = fake_linkedin.requests[-1]
    assert str(request.url) == "https://api.linkedin.com/rest/posts"
    assert request.headers["x-restli-protocol-version"] == "2.0.0"
    assert request.headers["linkedin-version"] == get_settings().linkedin_api_version

    payload = fake_linkedin.payload
    assert payload["author"] == f"urn:li:organization:{ORG_ID}"
    assert payload["visibility"] == "PUBLIC"
    assert payload["lifecycleState"] == "PUBLISHED"
    assert payload["distribution"]["feedDistribution"] == "MAIN_FEED"


async def test_an_over_long_post_is_refused_not_truncated(publishing, fake_linkedin):
    """Half a post in public is worse than an error someone can act on."""
    item = await _approved(publishing, body="x" * (li.MAX_COMMENTARY + 1))

    with pytest.raises(PublisherError, match="Shorten it"):
        await publishing.publish(item.id, actor="danish")
    assert fake_linkedin.requests == [], "nothing should have been transmitted"


async def test_escaping_counts_towards_the_limit(publishing, fake_linkedin):
    """A body under the limit can cross it once escaped. The check therefore runs on the
    rendered string, not the draft."""
    item = await _approved(publishing, body="(" * (li.MAX_COMMENTARY - 10))

    with pytest.raises(PublisherError, match="after escaping"):
        await publishing.publish(item.id, actor="danish")


# ── The gate ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("status", [
    ContentStatus.DRAFT, ContentStatus.IN_REVIEW, ContentStatus.CHANGES_REQUESTED,
])
async def test_unapproved_content_never_reaches_the_network(publishing, fake_linkedin, status):
    service = publishing.content
    item = await service.create(channel=ContentChannel.LINKEDIN, body=TRUE_COPY, actor="a")
    if status is not ContentStatus.DRAFT:
        await service.submit_for_review(item.id, actor="a")
    if status is ContentStatus.CHANGES_REQUESTED:
        await service.request_changes(item.id, actor="danish", feedback="more concrete")

    with pytest.raises(PublishRefused):
        await publishing.publish(item.id, actor="danish")
    assert fake_linkedin.requests == []


async def test_revising_after_approval_stops_the_post(publishing, fake_linkedin):
    item = await _approved(publishing)
    await publishing.content.revise(
        item.id, body=TRUE_COPY + " One more sentence nobody reviewed.",
        actor="agent", reason="tightened",
    )

    with pytest.raises(PublishRefused):
        await publishing.publish(item.id, actor="danish")
    assert fake_linkedin.requests == []


async def test_what_goes_out_is_the_approved_version_by_id(publishing, fake_linkedin):
    """The gate already refuses when approved and current differ. This asserts the
    stronger property: the words transmitted are looked up from `approved_version_id`, so
    a future change that moves `current_version_id` cannot redirect what gets posted."""
    item = await _approved(publishing, body="The approved words.")
    approved_id = item.approved_version_id

    await publishing.publish(item.id, actor="danish")

    stored = await publishing.content.get(item.id)
    approved = next(v for v in stored.versions if v.id == approved_id)
    assert approved.body in fake_linkedin.commentary


async def test_publishing_twice_is_refused_before_the_network(publishing, fake_linkedin):
    """A crash between the API call and the write would otherwise be 'repaired' by a retry
    that puts a second copy on the page."""
    item = await _approved(publishing)
    await publishing.publish(item.id, actor="danish")
    assert len(fake_linkedin.requests) == 1

    with pytest.raises(ValidationError, match="Already published"):
        await publishing.publish(item.id, actor="danish")
    assert len(fake_linkedin.requests) == 1


async def test_preview_transmits_nothing(publishing, fake_linkedin):
    item = await _approved(publishing)
    preview = await publishing.preview(item.id)

    assert fake_linkedin.requests == []
    assert preview["approved_by"] == "danish"
    assert preview["characters"] == len(preview["rendered"])
    assert (await publishing.content.get(item.id)).status is ContentStatus.APPROVED


async def test_a_channel_with_no_publisher_is_refused(publishing, fake_linkedin):
    """A new channel should require someone to write and test a publisher, not inherit
    one by accident."""
    item = await _approved(publishing, channel=ContentChannel.BLOG)

    with pytest.raises(ValidationError, match="publishes to blog"):
        await publishing.publish(item.id, actor="danish")


async def test_an_unconfigured_publisher_refuses(publishing, monkeypatch):
    monkeypatch.setattr(get_settings(), "linkedin_access_token", "")
    item = await _approved(publishing)

    with pytest.raises(PublisherError, match="not configured"):
        await publishing.publish(item.id, actor="danish")


# ── When the platform says no ─────────────────────────────────────────────────

async def test_an_expired_token_says_so_in_those_words(publishing, fake_linkedin):
    """A 401 here is almost always the 60-day expiry. "Unauthorized" alone sends whoever
    reads it hunting for a permissions problem that is not there."""
    fake_linkedin.status = 401
    item = await _approved(publishing)

    with pytest.raises(PublisherError, match="60 days"):
        await publishing.publish(item.id, actor="danish")
    assert (await publishing.content.get(item.id)).status is ContentStatus.APPROVED


@pytest.mark.parametrize("status,retryable", [(429, True), (503, True), (400, False),
                                              (403, False)])
async def test_failures_say_whether_retrying_could_help(publishing, fake_linkedin,
                                                        status, retryable):
    fake_linkedin.status = status
    item = await _approved(publishing)

    with pytest.raises(PublisherError) as caught:
        await publishing.publish(item.id, actor="danish")
    assert caught.value.retryable is retryable


async def test_a_201_with_no_id_is_an_error_not_a_success(publishing, fake_linkedin):
    """Published, but we cannot say what. Treating it as success would lose the only
    record of a live post."""
    fake_linkedin.headers = {}
    item = await _approved(publishing)

    with pytest.raises(PublisherError, match="no id"):
        await publishing.publish(item.id, actor="danish")


# ── The nasty case ────────────────────────────────────────────────────────────

async def test_a_live_post_is_recorded_even_when_recording_is_refused(
    publishing, fake_linkedin, monkeypatch
):
    """The worst state this system can reach: the post is public and the database thinks
    it is a draft. It must not be swallowed."""
    item = await _approved(publishing)

    async def _refuse(*args, **kwargs):
        raise PublishRefused("something changed underneath us")

    monkeypatch.setattr(ContentService, "mark_published", _refuse)

    with pytest.raises(PublishedButNotRecorded, match="Do not retry"):
        await publishing.publish(item.id, actor="danish")

    stored = await publishing.content.get(item.id)
    refusal = next(e for e in stored.events if e.event is ContentEventType.PUBLISH_REFUSED)
    assert POST_URN in refusal.note and "LIVE" in refusal.note, (
        "the trail has to carry the URL, or nobody can reconcile it"
    )


# ── The scheduler still asks ──────────────────────────────────────────────────

async def test_being_due_is_not_permission(publishing, fake_linkedin):
    """A scheduled item whose approval was invalidated must not go out because a timer
    fired."""
    from datetime import UTC, datetime, timedelta

    item = await _approved(publishing)
    await publishing.content.schedule(
        item.id, actor="danish", when=datetime.now(UTC) - timedelta(minutes=1)
    )
    await publishing.content.revise(
        item.id, body="changed after scheduling", actor="agent", reason="edit"
    )

    result = await publishing.publish_due()

    assert fake_linkedin.requests == []
    assert result["published"] == 0
    assert all(o["status"] == "skipped" for o in result["outcomes"])


async def test_one_bad_item_does_not_stop_the_queue(publishing, fake_linkedin):
    from datetime import UTC, datetime, timedelta

    due = datetime.now(UTC) - timedelta(minutes=1)
    good = await _approved(publishing, body="A perfectly fine post.")
    bad = await _approved(publishing, body="y" * (li.MAX_COMMENTARY + 1))
    for item in (good, bad):
        await publishing.content.schedule(item.id, actor="danish", when=due)

    result = await publishing.publish_due()

    by_id = {o["id"]: o["status"] for o in result["outcomes"]}
    assert by_id[str(good.id)] == "published"
    assert by_id[str(bad.id)] == "skipped"
    assert (result["published"], result["skipped"]) == (1, 1)


async def test_an_unknown_item_is_not_found(publishing):
    from app.services.exceptions import NotFoundError

    with pytest.raises(NotFoundError):
        await publishing.publish(uuid.uuid4(), actor="danish")


# ── Over HTTP ─────────────────────────────────────────────────────────────────

async def test_publish_over_http_records_the_url(client, admin_token, session_factory,
                                                 fake_linkedin):
    async with session_factory() as session:
        item = await _approved(PublishingService(session))

    response = await client.post(
        f"/api/v1/content/{item.id}/publish", json={"actor": "danish"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    assert response.json()["ref"] == POST_URN

    async with session_factory() as session:
        stored = await ContentService(session).get(item.id)
    assert stored.status is ContentStatus.PUBLISHED
    assert stored.published_url == f"https://www.linkedin.com/feed/update/{POST_URN}/"


async def test_publish_needs_the_admin_token(client, session_factory, fake_linkedin):
    async with session_factory() as session:
        item = await _approved(PublishingService(session))

    response = await client.post(
        f"/api/v1/content/{item.id}/publish", json={"actor": "anyone"}
    )

    assert response.status_code == 401
    assert fake_linkedin.requests == []


async def test_a_live_but_unrecorded_post_is_not_reported_as_skipped(
    publishing, fake_linkedin, monkeypatch
):
    """The scheduler's most dangerous outcome, and the one easiest to mislabel.

    Folded in with the failures it reads as "nothing happened" — while the post is public.
    Whoever sees the alert has to be told the opposite of that.
    """
    from datetime import UTC, datetime, timedelta

    item = await _approved(publishing)
    await publishing.content.schedule(
        item.id, actor="danish", when=datetime.now(UTC) - timedelta(minutes=1)
    )

    async def _refuse(*args, **kwargs):
        raise PublishRefused("something changed underneath us")

    monkeypatch.setattr(ContentService, "mark_published", _refuse)

    result = await publishing.publish_due()

    assert result["needs_attention"] == 1
    assert result["skipped"] == 0, "a public post must never be counted as skipped"
    assert result["outcomes"][0]["status"] == "published_but_not_recorded"
    assert POST_URN in result["outcomes"][0]["reason"]


async def test_the_counts_let_the_alerting_side_stay_dumb(publishing, fake_linkedin):
    """An n8n expression filtering an array is a place for a bug nobody will find."""
    result = await publishing.publish_due()

    assert result == {"considered": 0, "published": 0, "skipped": 0,
                      "needs_attention": 0, "summary": "", "outcomes": []}


async def test_a_quiet_run_produces_no_alert_text(publishing, fake_linkedin):
    """The scheduler runs every 15 minutes. An empty summary is what stops it saying
    "nothing to do" ninety-six times a day."""
    assert (await publishing.publish_due())["summary"] == ""


async def test_the_summary_leads_with_the_thing_to_act_on(publishing, fake_linkedin,
                                                          monkeypatch):
    """A live-but-unrecorded post outranks everything else in the message, including
    successful ones. It is the only line that means "go and do something right now"."""
    from datetime import UTC, datetime, timedelta
    due = datetime.now(UTC) - timedelta(minutes=1)

    item = await _approved(publishing)
    await publishing.content.schedule(item.id, actor="danish", when=due)

    async def _refuse(*a, **k):
        raise PublishRefused("changed underneath us")
    monkeypatch.setattr(ContentService, "mark_published", _refuse)

    summary = (await publishing.publish_due())["summary"]

    assert summary.startswith("🚨")
    assert "Do NOT retry" in summary
    assert POST_URN in summary


async def test_the_summary_names_published_urls_and_skip_reasons(publishing, fake_linkedin):
    from datetime import UTC, datetime, timedelta
    due = datetime.now(UTC) - timedelta(minutes=1)

    good = await _approved(publishing, body="A perfectly fine post.")
    bad = await _approved(publishing, body="y" * (li.MAX_COMMENTARY + 1))
    for item in (good, bad):
        await publishing.content.schedule(item.id, actor="danish", when=due)

    summary = (await publishing.publish_due())["summary"]

    assert "https://www.linkedin.com/feed/update/" in summary
    assert "Shorten it" in summary, "a bare count tells the reader nothing to act on"
