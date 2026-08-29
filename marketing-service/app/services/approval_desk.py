"""The approval desk: a draft, two buttons, and a reply lane.

This is the human half of the loop. The drafting agent writes, the claim checker refuses
what is false, and then a person decides — on their phone, in the ten seconds they have,
without opening a portal. Everything here exists to make that decision *informed* and
*attributable*.

Three things are load-bearing.

**A button carries a version id, not an item id.** The keyboard was rendered for specific
words. Tapping Approve means "I approve *these* words", so `callback_data` names the
version and `ContentService.approve` refuses if it is no longer current. A reviewer who
scrolls back to yesterday's message and taps Approve gets a refusal rather than silently
endorsing a draft that has since been rewritten. That property falls out of the design
instead of needing a guard.

**Every inbound update is proved to be from Telegram, then proved to be from someone
allowed.** Those are separate checks answering separate questions. The secret header says
the caller is Telegram; the sender allowlist says the human is one of ours. Passing the
first does not imply the second — anyone can message a bot, and Telegram delivers it.

**The desk edits its own message rather than replying to it.** A handled review stops
looking unhandled, the buttons disappear so a second tap cannot try an action that would
now be refused, and the outcome is recorded where the decision was made.

One documented limit: the buttons work from every allowed chat, but the free-text reply
lane is bound to the chat the draft was posted in, because a reply gives us a message id
and nothing else. A reply from elsewhere is answered with an explanation rather than a
guess — guessing which draft a note is about is precisely the mistake this system exists
to prevent.
"""
import logging
import uuid

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.content import ContentItem, ContentStatus, ContentVersion
from app.services.content import ContentService
from app.services.exceptions import NotConfiguredError, NotFoundError, ValidationError
from app.services.telegram import MAX_MESSAGE, TelegramNotifier, escape_html

logger = logging.getLogger("astra.mkt.desk")
settings = get_settings()

#: `callback_data` is capped at 64 bytes by Telegram. "ok:" plus a 32-character hex uuid
#: is 35, which leaves room and needs no encoding scheme to stay inside the limit.
_APPROVE = "ok"
_CHANGES = "no"

#: A draft can be a whole blog post. The review message keeps room for the metadata and
#: the outcome line that replaces the buttons later.
_MAX_BODY_IN_MESSAGE = 2800

_STATUS_LINE = {
    ContentStatus.DRAFT: "📝 Draft",
    ContentStatus.IN_REVIEW: "👀 Waiting for you",
    ContentStatus.CHANGES_REQUESTED: "✍️ Changes requested",
    ContentStatus.APPROVED: "✅ Approved",
    ContentStatus.SCHEDULED: "🕒 Scheduled",
    ContentStatus.PUBLISHED: "🚀 Published",
}


class DeskResult:
    """What the webhook endpoint should do next.

    `redraft_item_id` is set when a human left feedback and the drafting agent should
    rewrite. That is a model call taking tens of seconds, and Telegram redelivers any
    update it does not get a prompt answer to — so it is handed back for the endpoint to
    run *after* responding, never inline.
    """

    def __init__(self, handled: bool, note: str, redraft_item_id: uuid.UUID | None = None):
        self.handled = handled
        self.note = note
        self.redraft_item_id = redraft_item_id


class ApprovalDesk:
    def __init__(self, session) -> None:
        self.session = session
        self.content = ContentService(session)
        self.telegram = TelegramNotifier()

    @property
    def enabled(self) -> bool:
        return self.telegram.enabled

    # ── Outbound: put a draft in front of a person ────────────────────────────

    def compose_review(self, item: ContentItem, version: ContentVersion) -> str:
        """The message a reviewer actually reads.

        Ordered by what a decision needs: what this is, why it was written that way, the
        words themselves, then anything the checker flagged but did not block. The
        warnings sit *below* the draft on purpose — read the copy first, then the caveats,
        rather than being primed to look for problems in text you have not read.
        """
        head = f"<b>{_STATUS_LINE.get(item.status, '📝 Draft')} · {item.channel.value}</b>"
        if item.campaign:
            head += f" · {escape_html(item.campaign)}"

        lines = [f"{head}  <i>v{version.version_number}</i>", ""]

        if version.revision_reason:
            lines += [f"<i>Revising: {escape_html(version.revision_reason)}</i>", ""]

        if version.headline:
            lines += [f"<b>{escape_html(version.headline)}</b>", ""]

        body = version.body.strip()
        if len(body) > _MAX_BODY_IN_MESSAGE:
            body = body[:_MAX_BODY_IN_MESSAGE] + "\n\n… (truncated — open the API for the rest)"
        lines.append(escape_html(body))

        if version.hashtags:
            lines += ["", f"<i>{escape_html(version.hashtags)}</i>"]
        if version.cta:
            lines += ["", f"👉 {escape_html(version.cta)}"]

        warnings = self._warnings(version)
        if warnings:
            lines += ["", "<b>Worth a look before you approve:</b>"]
            lines += [f"• {escape_html(w)}" for w in warnings]

        return "\n".join(lines)[:MAX_MESSAGE]

    @staticmethod
    def _warnings(version: ContentVersion) -> list[str]:
        """Warnings as stored at the time this version was written.

        Read from the version's own `check_result` rather than re-run. Re-running would
        answer a question about today's rules, and the reviewer needs to see what was true
        about these words when they were written.
        """
        stored = version.check_result or {}
        return [str(w) for w in stored.get("warnings", [])]

    def keyboard(self, version: ContentVersion) -> dict:
        return {"inline_keyboard": [[
            {"text": f"✅ Approve v{version.version_number}",
             "callback_data": f"{_APPROVE}:{version.id.hex}"},
            {"text": "✍️ Request changes",
             "callback_data": f"{_CHANGES}:{version.id.hex}"},
        ]]}

    async def post_for_review(self, item: ContentItem) -> bool:
        """Send the current version to every allowed chat, with buttons.

        The item must already be IN_REVIEW: submitting is what runs the blocking claim
        check, and a draft that failed it must never reach a person. Asking someone to
        weigh a forbidden claim under time pressure turns the checker's findings into one
        more thing to click past.
        """
        if not self.enabled:
            logger.debug("desk not configured; not posting %s for review", item.id)
            return False
        if item.status is not ContentStatus.IN_REVIEW:
            raise ValidationError(
                f"Only content in review goes to the desk; this is {item.status.value}."
            )

        version = await self.content.current_version(item)
        if version is None:
            raise ValidationError("Nothing to review.")

        text = self.compose_review(item, version)
        keyboard = self.keyboard(version)

        first_message_id: int | None = None
        first_chat_id: str | None = None
        for chat_id in self.telegram.chat_ids:
            message_id = await self.telegram.send_message(chat_id, text, keyboard)
            if message_id is not None and first_message_id is None:
                first_message_id, first_chat_id = message_id, chat_id

        if first_message_id is None:
            logger.warning("desk could not post %s to any chat", item.id)
            return False

        # Overwritten each time a new version goes out, so a reply to a superseded message
        # finds nothing. That is the right answer: the conversation moved on, and applying
        # the note would edit words the sender was not looking at.
        item.review_message_id = first_message_id
        item.review_chat_id = first_chat_id
        await self.session.commit()
        return True

    # ── Inbound: someone pressed something ───────────────────────────────────

    async def handle_update(self, update: dict) -> DeskResult:
        """Route one Telegram update. Never raises — see DeskResult."""
        try:
            if "callback_query" in update:
                return await self._handle_callback(update["callback_query"])
            if "message" in update:
                return await self._handle_message(update["message"])
        except Exception:
            # A traceback escaping here becomes a non-200, and a non-200 makes Telegram
            # redeliver — turning one bug into an endless loop of retries.
            logger.exception("desk failed to handle an update")
            return DeskResult(False, "error")
        return DeskResult(False, "ignored")

    def _allowed(self, sender: dict | None) -> bool:
        """Is this human one of ours?

        Separate from the secret-header check, which only proves the *caller* is Telegram.
        Anyone in the world can message a bot and Telegram will faithfully deliver it, so
        without this the header would be authenticating the postman rather than the sender.
        """
        return str((sender or {}).get("id", "")) in self.telegram.chat_ids

    @staticmethod
    def _who(sender: dict) -> str:
        """A name for the audit trail. Never 'the system' — see the gate's own tests."""
        name = " ".join(filter(None, [sender.get("first_name"), sender.get("last_name")]))
        handle = sender.get("username")
        label = name or handle or "unknown"
        return f"telegram:{label} ({sender.get('id')})"

    async def _handle_callback(self, query: dict) -> DeskResult:
        query_id = query.get("id", "")
        sender = query.get("from") or {}

        if not self._allowed(sender):
            logger.warning("desk refused a callback from %s", sender.get("id"))
            await self.telegram.answer_callback(query_id, "Not authorised.")
            return DeskResult(False, "refused")

        action, _, version_hex = (query.get("data") or "").partition(":")
        try:
            version_id = uuid.UUID(hex=version_hex)
        except ValueError:
            await self.telegram.answer_callback(query_id, "I don't understand that button.")
            return DeskResult(False, "bad-callback-data")

        item = await self._item_for_version(version_id)
        if item is None:
            await self.telegram.answer_callback(query_id, "That draft no longer exists.")
            return DeskResult(False, "unknown-version")

        message = query.get("message") or {}
        chat_id = str((message.get("chat") or {}).get("id", ""))
        message_id = message.get("message_id")

        if action == _APPROVE:
            return await self._approve(item, version_id, sender, query_id, chat_id, message_id)
        if action == _CHANGES:
            return await self._ask_for_changes(item, sender, query_id, chat_id, message_id)

        await self.telegram.answer_callback(query_id, "Unknown action.")
        return DeskResult(False, "unknown-action")

    async def _approve(
        self, item: ContentItem, version_id: uuid.UUID, sender: dict,
        query_id: str, chat_id: str, message_id: int | None,
    ) -> DeskResult:
        actor = self._who(sender)
        try:
            await self.content.approve(item.id, actor=actor, version_id=version_id)
        except ValidationError as exc:
            # The common case is a second tap on a message that was already handled, or a
            # tap on a superseded version. Both are answered with the reason rather than
            # swallowed: a button that does nothing and says nothing is worse than one
            # that refuses out loud.
            await self.telegram.answer_callback(query_id, str(exc)[:200])
            return DeskResult(True, "refused")

        logger.info("content %s approved by %s", item.id, actor)
        await self.telegram.answer_callback(query_id, "Approved.")
        if message_id is not None:
            fresh = await self.content.get(item.id)
            version = await self.content.current_version(fresh)
            by = escape_html(sender.get("first_name") or "")
            await self._settle(chat_id, message_id, fresh, version,
                               f"✅ <b>Approved</b> by {by}")
        return DeskResult(True, "approved")

    async def _ask_for_changes(
        self, item: ContentItem, sender: dict, query_id: str,
        chat_id: str, message_id: int | None,
    ) -> DeskResult:
        """Turn the review message into a prompt for a note.

        The message is edited rather than answered with a new one, so `review_message_id`
        stays pointing at the same message and the reply the person is about to type is
        unambiguously about this draft.
        """
        await self.telegram.answer_callback(query_id, "Reply with what to change.")

        if message_id is not None:
            version = await self.content.current_version(item)
            await self._settle(
                chat_id, message_id, item, version,
                "✍️ <b>Reply to this message</b> with what to change.",
            )
            # Whichever chat the reviewer is acting from is now the reply lane, even if
            # the draft was first posted elsewhere. Follow the person, not the record.
            item.review_message_id = message_id
            item.review_chat_id = chat_id
            await self.session.commit()
        return DeskResult(True, "awaiting-feedback")

    async def _settle(
        self, chat_id: str, message_id: int, item: ContentItem,
        version: ContentVersion | None, outcome: str,
    ) -> None:
        """Rewrite a review message with its outcome and no buttons."""
        body = self.compose_review(item, version) if version is not None else ""
        text = f"{body}\n\n{'─' * 12}\n{outcome}"
        await self.telegram.edit_message(chat_id, message_id, text)

    async def _handle_message(self, message: dict) -> DeskResult:
        """A free-text reply: treat it as feedback on the draft it answers."""
        sender = message.get("from") or {}
        text = (message.get("text") or "").strip()
        replied_to = (message.get("reply_to_message") or {}).get("message_id")
        chat_id = str((message.get("chat") or {}).get("id", ""))

        if not self._allowed(sender) or not text or replied_to is None:
            return DeskResult(False, "ignored")

        item = await self._item_for_message(chat_id, replied_to)
        if item is None:
            await self.telegram.send_message(
                chat_id,
                "I can't tell which draft that's about — it isn't the message I'm "
                "currently waiting on. Use the buttons on the latest draft.",
            )
            return DeskResult(False, "unmatched-reply")

        actor = self._who(sender)
        try:
            await self.content.request_changes(item.id, actor=actor, feedback=text)
        except ValidationError as exc:
            await self.telegram.send_message(
                chat_id, f"Couldn't record that: {escape_html(str(exc))}"
            )
            return DeskResult(False, "refused")

        logger.info("content %s: changes requested by %s", item.id, actor)

        from app.services.drafting import DraftingAgent
        if not DraftingAgent().enabled:
            await self.telegram.send_message(
                chat_id, "Noted — saved against this draft. (Rewriting needs an API key.)"
            )
            return DeskResult(True, "feedback-recorded")

        await self.telegram.send_message(chat_id, "Got it — rewriting now.")
        return DeskResult(True, "redrafting", redraft_item_id=item.id)

    # ── Lookups ──────────────────────────────────────────────────────────────

    async def _item_for_version(self, version_id: uuid.UUID) -> ContentItem | None:
        version = (await self.session.execute(
            select(ContentVersion).where(ContentVersion.id == version_id)
        )).scalar_one_or_none()
        if version is None:
            return None
        try:
            return await self.content.get(version.content_item_id)
        except NotFoundError:
            return None

    async def _item_for_message(self, chat_id: str, message_id: int) -> ContentItem | None:
        """Both halves of the pair, never the message id alone.

        Telegram numbers messages per chat, so ids collide across chats. Matching on the
        id by itself would let a reply in one chat attach feedback to a draft posted in
        another.
        """
        return (await self.session.execute(
            select(ContentItem).where(
                ContentItem.review_message_id == message_id,
                ContentItem.review_chat_id == chat_id,
            )
        )).scalar_one_or_none()


async def redraft_and_repost(item_id: uuid.UUID) -> None:
    """Rewrite against the recorded feedback and put the result back on the desk.

    Runs after the webhook has already answered Telegram, in its own session — the
    request's session is closed by then. Failures are logged and reported to the desk
    rather than raised: nobody is watching a stack trace, and a person who was told
    "rewriting now" needs to hear if it did not happen.
    """
    from app.services.drafting import DraftingAgent

    async with SessionLocal() as session:
        desk = ApprovalDesk(session)
        service = desk.content
        try:
            item = await service.get(item_id)
            version = await service.current_version(item)
            if version is None:
                return

            feedback = _latest_feedback(item)
            result = await DraftingAgent().revise(
                channel=item.channel, previous=version.body,
                feedback=feedback, brief=item.brief,
            )
            await service.revise(
                item_id, body=result.draft.body, headline=result.draft.headline,
                hashtags=result.draft.hashtags, cta=result.draft.cta,
                actor="drafting-agent", reason=feedback,
                authored_by=f"{settings.drafting_model} (revision)",
            )

            item = await service.get(item_id)
            if result.blocked:
                # The rewrite states something the product does not do. Submitting would
                # be refused by the claim check anyway; saying so is more useful than a
                # silent stall, and it is a fact about the feedback worth seeing.
                await _tell(desk, item,
                            "⚠️ The rewrite made a claim ASTRA can't support, so it hasn't "
                            "gone to review. Try being more specific about what to change.")
                return

            await service.submit_for_review(item_id, actor="drafting-agent")
            await desk.post_for_review(await service.get(item_id))
        except (NotFoundError, ValidationError, NotConfiguredError) as exc:
            logger.warning("redraft of %s failed: %s", item_id, exc)
            await _notify_failure(desk, item_id, str(exc))
        except Exception as exc:  # noqa: BLE001 — background task; nothing above catches
            logger.exception("redraft of %s failed", item_id)
            await _notify_failure(desk, item_id, f"{type(exc).__name__}: {exc}")


def _latest_feedback(item: ContentItem) -> str:
    """The note that triggered this rewrite, verbatim.

    Paraphrasing feedback before acting on it is how a revision ends up answering a note
    nobody wrote — the same reason `DraftingAgent.revise` quotes it between markers.
    """
    from app.models.content import ContentEventType

    notes = [e.note for e in item.events
             if e.event is ContentEventType.CHANGES_REQUESTED and e.note]
    return notes[-1] if notes else "Make it better."


async def _tell(desk: ApprovalDesk, item: ContentItem, text: str) -> None:
    chat_id = item.review_chat_id or (desk.telegram.chat_ids or [None])[0]
    if chat_id:
        await desk.telegram.send_message(chat_id, text)


async def _notify_failure(desk: ApprovalDesk, item_id: uuid.UUID, reason: str) -> None:
    for chat_id in desk.telegram.chat_ids:
        await desk.telegram.send_message(
            chat_id, f"❌ Couldn't rewrite that draft.\n<code>{escape_html(reason)[:300]}</code>"
        )
        break
