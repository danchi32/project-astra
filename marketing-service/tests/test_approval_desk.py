"""The approval desk.

This is the service's second publicly-reachable write endpoint, and the only one that can
approve marketing copy. The lead intake endpoint can at worst create a junk row; this one
decides what the company says in public. So the tests are weighted accordingly: most of
them are about who is allowed to do what, and the rest are about the one property the
whole design rests on — that a button approves the words it was rendered for.

Nothing here touches the network. `FakeTelegram` records what would have been sent, which
is also how the message-composition assertions get something to look at.
"""
import uuid

import pytest
import pytest_asyncio

from app.core.config import get_settings
from app.models.content import ContentChannel, ContentEventType, ContentStatus
from app.services.approval_desk import ApprovalDesk
from app.services.content import ContentService
from app.services.telegram import TelegramNotifier

TRUE_COPY = (
    "ASTRA gathers endpoint evidence before it proposes a fix. Remediations are tiered, "
    "and the tier is enforced server-side."
)

DESK_CHAT = "111"
SECOND_CHAT = "222"
WEBHOOK_SECRET = "test-webhook-secret"

ALLOWED = {"id": 111, "first_name": "Danish", "username": "danchi32"}
STRANGER = {"id": 999, "first_name": "Mallory", "username": "not_invited"}


class FakeTelegram:
    """Stands in for Telegram's HTTP API, recording every call."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.photos: list[dict] = []
        self.edited: list[dict] = []
        self.answered: list[dict] = []
        self._next_id = 1000

    async def send_photo(self, chat_id, png, caption=None):
        self._next_id += 1
        self.photos.append({"chat_id": chat_id, "png": png, "caption": caption,
                            "message_id": self._next_id})
        return self._next_id

    async def send_message(self, chat_id, text, keyboard=None):
        self._next_id += 1
        self.sent.append({"chat_id": chat_id, "text": text,
                          "keyboard": keyboard, "message_id": self._next_id})
        return self._next_id

    async def edit_message(self, chat_id, message_id, text, keyboard=None):
        self.edited.append({"chat_id": chat_id, "message_id": message_id,
                            "text": text, "keyboard": keyboard})
        return True

    async def answer_callback(self, callback_query_id, text=""):
        self.answered.append({"id": callback_query_id, "text": text})
        return True

    # Read by ApprovalDesk exactly as the real notifier's are.
    enabled = True
    chat_ids = [DESK_CHAT, SECOND_CHAT]

    @property
    def last_answer(self) -> str:
        return self.answered[-1]["text"] if self.answered else ""


@pytest.fixture
def telegram(monkeypatch) -> FakeTelegram:
    """Turn the desk on, with a fake wire.

    Settings are lru_cached, so every module holds the same object and patching its
    attributes here reaches all of them. The conftest empties these for the whole suite;
    this fixture is the deliberate, scoped exception.
    """
    fake = FakeTelegram()
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", "test-token")
    monkeypatch.setattr(settings, "telegram_chat_ids", f"{DESK_CHAT},{SECOND_CHAT}")
    monkeypatch.setattr(settings, "telegram_webhook_secret", WEBHOOK_SECRET)

    for name in ("send_message", "send_photo", "edit_message", "answer_callback"):
        monkeypatch.setattr(TelegramNotifier, name, getattr(fake, name))
    return fake


@pytest_asyncio.fixture
async def desk(session_factory, telegram):
    async with session_factory() as session:
        yield ApprovalDesk(session)


async def _in_review(desk: ApprovalDesk, body: str = TRUE_COPY):
    """A draft sitting on the desk, exactly as submitting would leave it."""
    service: ContentService = desk.content
    item = await service.create(
        channel=ContentChannel.LINKEDIN, body=body, actor="drafting-agent",
    )
    await service.submit_for_review(item.id, actor="drafting-agent")
    item = await service.get(item.id)
    await desk.post_for_review(item)
    return await service.get(item.id)


def _callback(action: str, version_id, sender=ALLOWED, chat=DESK_CHAT, message_id=1001):
    return {"callback_query": {
        "id": "cbq-1",
        "from": sender,
        "data": f"{action}:{version_id.hex}",
        "message": {"message_id": message_id, "chat": {"id": int(chat)}},
    }}


def _reply(text: str, to_message_id: int, sender=ALLOWED, chat=DESK_CHAT):
    return {"message": {
        "message_id": 5000,
        "from": sender,
        "chat": {"id": int(chat)},
        "text": text,
        "reply_to_message": {"message_id": to_message_id},
    }}


# ── Who is allowed to act ─────────────────────────────────────────────────────

async def test_a_stranger_cannot_approve(desk, telegram):
    """The header proves the caller is Telegram. It says nothing about the human.

    Anyone in the world can message a bot, and Telegram delivers it faithfully. Without
    this check the secret token would be authenticating the postman.
    """
    item = await _in_review(desk)
    result = await desk.handle_update(
        _callback("ok", item.current_version_id, sender=STRANGER)
    )

    assert result.handled is False
    assert "authorised" in telegram.last_answer.lower()
    assert (await desk.content.get(item.id)).status is ContentStatus.IN_REVIEW


async def test_a_stranger_cannot_leave_feedback(desk):
    item = await _in_review(desk)
    result = await desk.handle_update(
        _reply("change everything", item.review_message_id, sender=STRANGER)
    )

    assert result.handled is False
    assert (await desk.content.get(item.id)).status is ContentStatus.IN_REVIEW


async def test_an_allowed_reviewer_approves(desk, telegram):
    item = await _in_review(desk)
    approved_version = item.current_version_id

    result = await desk.handle_update(_callback("ok", approved_version))

    assert result.handled is True
    stored = await desk.content.get(item.id)
    assert stored.status is ContentStatus.APPROVED
    assert stored.approved_version_id == approved_version
    assert "Danish" in stored.approved_by and "111" in stored.approved_by, (
        "the trail has to name a person; 'the system approved it' is the answer that "
        "makes an audit trail worthless"
    )


# ── The property the whole design rests on ────────────────────────────────────

async def test_the_button_approves_the_words_it_was_rendered_for(desk, telegram):
    """Scroll back to yesterday's message, tap Approve, and get a refusal.

    The keyboard carries a version id because it was drawn for specific words. Had it
    carried the item id, this tap would have endorsed a draft the reviewer never read —
    and every step would look legitimate in the log afterwards.
    """
    item = await _in_review(desk)
    stale_button = _callback("ok", item.current_version_id)

    # The draft is rewritten. It stays in review — nothing was approved, so there is no
    # approval to clear — but the current version has moved, and the old message with its
    # old button is still sitting on the reviewer's phone.
    await desk.content.revise(
        item.id, body=TRUE_COPY + " Now with an extra sentence.",
        actor="drafting-agent", reason="tightened",
    )
    await desk.post_for_review(await desk.content.get(item.id))

    result = await desk.handle_update(stale_button)

    assert result.note == "refused"
    assert "no longer current" in telegram.last_answer
    stored = await desk.content.get(item.id)
    assert stored.status is ContentStatus.IN_REVIEW
    assert stored.approved_version_id is None


async def test_tapping_approve_twice_does_not_reassign_the_approval(desk, telegram):
    """Telegram redelivers, and fingers slip. The second tap must be inert."""
    item = await _in_review(desk)
    version_id = item.current_version_id

    await desk.handle_update(_callback("ok", version_id))
    first_approver = (await desk.content.get(item.id)).approved_by

    result = await desk.handle_update(_callback("ok", version_id, sender=STRANGER | {"id": 222}))

    assert result.note == "refused"
    stored = await desk.content.get(item.id)
    assert stored.approved_by == first_approver
    assert telegram.last_answer, "a button that refuses silently looks broken"


async def test_approving_through_the_desk_satisfies_the_publish_gate(desk):
    """End to end: what the desk produces is what the gate accepts. Nothing else is."""
    item = await _in_review(desk)
    await desk.handle_update(_callback("ok", item.current_version_id))

    await desk.content.mark_published(item.id, actor="publisher", url="https://x.test/1")
    assert (await desk.content.get(item.id)).status is ContentStatus.PUBLISHED


async def test_a_draft_that_failed_the_claim_check_never_reaches_the_desk(desk, telegram):
    """Submitting runs the blocking check, so the desk only ever sees copy that passed."""
    from app.services.exceptions import ValidationError

    item = await desk.content.create(
        channel=ContentChannel.LINKEDIN, actor="drafting-agent",
        body="Certificate-based enrollment for every agent, with fully autonomous fixes.",
    )
    with pytest.raises(ValidationError):
        await desk.content.submit_for_review(item.id, actor="drafting-agent")

    assert telegram.sent == [], "a forbidden claim must not be put in front of a human"


# ── The reply lane ────────────────────────────────────────────────────────────

async def test_a_reply_is_recorded_verbatim_as_feedback(desk):
    item = await _in_review(desk)
    note = "Cut the second paragraph and name the customer."

    await desk.handle_update(_reply(note, item.review_message_id))

    stored = await desk.content.get(item.id)
    assert stored.status is ContentStatus.CHANGES_REQUESTED
    recorded = [e.note for e in stored.events
                if e.event is ContentEventType.CHANGES_REQUESTED]
    assert recorded == [note], (
        "paraphrasing feedback before acting on it is how a revision answers a note "
        "nobody wrote"
    )


async def test_a_reply_in_another_chat_does_not_match(desk, telegram):
    """Telegram numbers messages per chat, so ids collide across chats.

    Matching on the message id alone would let a reply in one chat attach feedback to a
    draft posted in another.
    """
    item = await _in_review(desk)
    result = await desk.handle_update(
        _reply("shorter please", item.review_message_id, chat=SECOND_CHAT)
    )

    assert result.note == "unmatched-reply"
    assert (await desk.content.get(item.id)).status is ContentStatus.IN_REVIEW
    assert "can't tell which draft" in telegram.sent[-1]["text"]


async def test_a_reply_to_a_superseded_message_does_not_match(desk):
    """The conversation moved on. Applying the note would edit words the sender was not
    looking at."""
    item = await _in_review(desk)
    old_message_id = item.review_message_id

    await desk.content.revise(item.id, body=TRUE_COPY + " v2", actor="agent", reason="r")
    await desk.post_for_review(await desk.content.get(item.id))

    result = await desk.handle_update(_reply("older note", old_message_id))
    assert result.note == "unmatched-reply"


async def test_request_changes_turns_the_message_into_a_prompt(desk, telegram):
    """Edited, not answered with a new message — so the id the reply will carry still
    points at this draft."""
    item = await _in_review(desk)

    await desk.handle_update(_callback("no", item.current_version_id))

    assert telegram.edited, "the review message should have been rewritten in place"
    assert "Reply to this message" in telegram.edited[-1]["text"]
    assert telegram.edited[-1]["keyboard"] is None, "a handled review stops offering buttons"


async def test_the_reply_lane_follows_the_reviewer_to_their_own_chat(desk):
    """Buttons work from any allowed chat; the reply lane rebinds to wherever they acted."""
    item = await _in_review(desk)
    assert item.review_chat_id == DESK_CHAT

    await desk.handle_update(
        _callback("no", item.current_version_id, chat=SECOND_CHAT, message_id=7777)
    )

    stored = await desk.content.get(item.id)
    assert (stored.review_chat_id, stored.review_message_id) == (SECOND_CHAT, 7777)

    await desk.handle_update(_reply("tighter", 7777, chat=SECOND_CHAT))
    assert (await desk.content.get(item.id)).status is ContentStatus.CHANGES_REQUESTED


# ── Malformed input reaches no state ──────────────────────────────────────────

@pytest.mark.parametrize("update", [
    {},
    {"message": {}},
    {"callback_query": {"id": "x", "from": ALLOWED, "data": "garbage"}},
    {"callback_query": {"id": "x", "from": ALLOWED, "data": "ok:not-a-uuid"}},
    {"callback_query": {"id": "x", "from": ALLOWED, "data": f"ok:{uuid.uuid4().hex}"}},
    {"callback_query": {"id": "x", "from": ALLOWED, "data": None}},
    {"message": {"from": ALLOWED, "chat": {"id": 111}, "text": "hello"}},   # not a reply
])
async def test_junk_updates_are_handled_without_raising(desk, update):
    """A traceback escaping the handler becomes a non-200, and a non-200 makes Telegram
    redeliver — turning one bug into an endless retry loop."""
    result = await desk.handle_update(update)
    assert result.handled is False


# ── What the reviewer actually sees ───────────────────────────────────────────

async def test_the_review_shows_the_version_number_on_the_button(desk, telegram):
    item = await _in_review(desk)
    button = telegram.sent[0]["keyboard"]["inline_keyboard"][0][0]

    assert button["text"] == "✅ Approve v1", "'approve v2' has to mean one thing"
    assert button["callback_data"] == f"ok:{item.current_version_id.hex}"
    assert len(button["callback_data"].encode()) <= 64, "Telegram's hard limit"


async def test_the_draft_is_posted_to_every_allowed_chat(desk, telegram):
    await _in_review(desk)
    assert {m["chat_id"] for m in telegram.sent} == {DESK_CHAT, SECOND_CHAT}


async def test_attacker_controlled_text_is_escaped(desk, telegram):
    """A draft can quote a prospect's own words. Unescaped, `<b>` would at best corrupt
    the review and at worst make Telegram reject it — so the reviewer would silently stop
    being shown exactly the drafts crafted to avoid them."""
    item = await desk.content.create(
        channel=ContentChannel.LINKEDIN, actor="agent",
        body=TRUE_COPY + ' <script>alert("x")</script> & <b>bold</b>',
    )
    await desk.content.submit_for_review(item.id, actor="agent")
    await desk.post_for_review(await desk.content.get(item.id))

    text = telegram.sent[-1]["text"]
    assert "&lt;script&gt;" in text and "<script>" not in text
    assert "&amp;" in text


async def test_the_desk_refuses_to_post_something_not_in_review(desk):
    from app.services.exceptions import ValidationError

    item = await desk.content.create(
        channel=ContentChannel.BLOG, body=TRUE_COPY, actor="agent"
    )
    with pytest.raises(ValidationError, match="Only content in review"):
        await desk.post_for_review(item)


# ── The webhook door ──────────────────────────────────────────────────────────

async def test_the_webhook_is_shut_when_no_secret_is_configured(client, monkeypatch):
    """Unset means shut, not open. A missing credential must never be the thing that
    produces a public endpoint able to approve marketing copy."""
    monkeypatch.setattr(get_settings(), "telegram_webhook_secret", "")
    response = await client.post("/api/v1/telegram/webhook", json={})
    assert response.status_code == 503


async def test_the_webhook_rejects_a_missing_secret(client, telegram):
    response = await client.post("/api/v1/telegram/webhook", json={})
    assert response.status_code == 401


async def test_the_webhook_rejects_a_wrong_secret(client, telegram):
    response = await client.post(
        "/api/v1/telegram/webhook", json={},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )
    assert response.status_code == 401


async def test_the_webhook_accepts_the_configured_secret(client, telegram):
    response = await client.post(
        "/api/v1/telegram/webhook", json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
    )
    assert response.status_code == 200


async def test_an_unparseable_body_is_answered_200(client, telegram):
    """Refusing it would have Telegram redeliver the same broken body forever."""
    response = await client.post(
        "/api/v1/telegram/webhook", content=b"not json",
        headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET,
                 "Content-Type": "application/json"},
    )
    assert response.status_code == 200


async def test_approval_works_over_http(client, session_factory, telegram):
    """The whole path, through the real endpoint."""
    async with session_factory() as session:
        item = await _in_review(ApprovalDesk(session))

    response = await client.post(
        "/api/v1/telegram/webhook",
        json=_callback("ok", item.current_version_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
    )

    assert response.status_code == 200 and response.json()["handled"] is True
    async with session_factory() as session:
        stored = await ContentService(session).get(item.id)
    assert stored.status is ContentStatus.APPROVED


async def test_submitting_puts_it_on_the_desk(client, admin_token, session_factory, telegram):
    """Posting is part of submitting. "Submitted for review" sitting in a table nobody
    opens is how a queue silently becomes a graveyard."""
    async with session_factory() as session:
        item = await ContentService(session).create(
            channel=ContentChannel.LINKEDIN, body=TRUE_COPY, actor="agent",
        )

    response = await client.post(
        f"/api/v1/content/{item.id}/submit", json={"actor": "danish"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    assert telegram.sent, "submitting should have posted it to the desk"
    assert telegram.sent[0]["keyboard"] is not None


async def test_telegram_being_down_does_not_undo_a_submission(
    client, admin_token, session_factory, telegram, monkeypatch
):
    """The post is best-effort and comes after the transition. An unreachable Telegram
    must not roll back a submission that already passed the claim check."""
    async def _explode(*args, **kwargs):
        raise RuntimeError("telegram is down")

    monkeypatch.setattr(TelegramNotifier, "send_message", _explode)

    async with session_factory() as session:
        item = await ContentService(session).create(
            channel=ContentChannel.LINKEDIN, body=TRUE_COPY, actor="agent",
        )

    response = await client.post(
        f"/api/v1/content/{item.id}/submit", json={"actor": "danish"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    async with session_factory() as session:
        assert (await ContentService(session).get(item.id)).status is ContentStatus.IN_REVIEW


# ── The card goes with it ─────────────────────────────────────────────────────

async def test_the_card_is_sent_before_the_copy(desk, telegram):
    """A reviewer approving a post is approving its image too, so they have to have seen
    it. Sending the picture first puts it above the copy in the conversation."""
    await _in_review(desk)

    assert telegram.photos, "no image reached the desk"
    assert telegram.photos[0]["png"][:4] == bytes([0x89, 0x50, 0x4E, 0x47]), "not a PNG"
    assert {p["chat_id"] for p in telegram.photos} == {DESK_CHAT, SECOND_CHAT}


async def test_the_buttons_stay_on_the_text_message(desk, telegram):
    """Not on the photo. The buttons and the reply lane have to live on the same message,
    and review_message_id points at the one a reply attaches to."""
    item = await _in_review(desk)

    assert telegram.photos[0]["caption"] is None
    assert telegram.sent[0]["keyboard"] is not None
    assert item.review_message_id == telegram.sent[0]["message_id"]


async def test_a_card_that_will_not_draw_does_not_block_the_review(desk, telegram,
                                                                   monkeypatch):
    """An image problem is a smaller problem than a review queue that stops moving."""
    import app.services.cards as cards

    def _explode(*args, **kwargs):
        raise OSError("no font in this container")

    monkeypatch.setattr(cards, "render", _explode)

    item = await _in_review(desk)

    assert telegram.photos == []
    assert telegram.sent, "the copy still has to reach a human"
    assert item.review_message_id is not None
