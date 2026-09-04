import json
import re
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import (
    Conversation,
    Device,
    Message,
    MessageRole,
    Organization,
    RemediationTask,
    User,
)
from app.models.base import as_utc, utcnow
from app.repositories.conversations import ConversationRepository, MessageRepository
from app.repositories.organizations import OrganizationRepository
from app.services.ai.cache import SemanticCache
from app.services.ai.cognitive import CognitiveEngine
from app.services.ai.intent import (
    OFF_TOPIC_REPLY,
    is_off_topic,
    reports_still_broken,
    requires_live_action,
)
from app.services.ai.learned import LearnedFixStore, created_task_ids
from app.services.ai.provider import (
    LearnedActionProvider,
    LLMProvider,
    StubProvider,
    get_provider,
)
from app.services.agent_update import AgentUpdateService
from app.services.assistants import AssistantService
from app.services.exceptions import NotFoundError
from app.services.subscription import org_is_writable

# "What version are you?" asked of the ASTRA agent itself — answered directly with the
# device's real agent version, never routed to the generic assistant reply.
_VERSION_WORD = re.compile(r"\b(version|build|v\d)\b", re.IGNORECASE)
_VERSION_SUBJECT = ("your", "you", "astra", "agent", "assistant", "yourself", "u r", "ur ")
_VERSION_EXCLUDE = (
    "windows", " os ", "driver", "office", "chrome", "edge", "outlook", "teams",
    "zoom", "app version", "software version", "python", "node", ".net",
)


def _is_version_question(text: str) -> bool:
    t = f" {text.lower().strip()} "
    if not _VERSION_WORD.search(t):
        return False
    if any(w in t for w in _VERSION_EXCLUDE):
        return False   # asking about the OS / another app, not the agent
    return any(w in t for w in _VERSION_SUBJECT)

# Shown in the tray when the org can't use chat (suspended, past due, canceled, or
# an expired trial). No LLM call and no remediation — chat simply doesn't function.
_SUBSCRIPTION_INACTIVE_REPLY = (
    "ASTRA support chat is unavailable because your organization's subscription is "
    "inactive. Please contact your IT administrator to restore access."
)


@dataclass
class Reply:
    text: str
    tool_trail: list[dict[str, Any]] | None
    # Where the answer came from: "intent_gate" and "cache" cost no LLM call.
    source: str


class ConversationService:
    def __init__(self, session: AsyncSession, provider: LLMProvider | None = None) -> None:
        self.session = session
        self.conversations = ConversationRepository(session)
        self.messages = MessageRepository(session)
        self.orgs = OrganizationRepository(session)
        # An injected provider (tests) is always used; otherwise the provider is
        # chosen per-message in _select_provider so common issues stay free.
        self._forced_provider = provider
        self.cache = SemanticCache(session)
        self.learned = LearnedFixStore(session)

    async def create(self, *, actor: User, title: str) -> Conversation:
        conversation = await self.conversations.add(
            Conversation(org_id=actor.org_id, user_id=actor.id, title=title)
        )
        await self.session.commit()
        return conversation

    async def list_for_user(self, *, actor: User) -> list[Conversation]:
        return await self.conversations.list_by_user(actor.id)

    async def get_messages(self, *, actor: User, conversation_id: uuid.UUID) -> list[Message]:
        await self._get_owned(actor, conversation_id)
        return await self.messages.list_by_conversation(conversation_id)

    async def send_message(
        self, *, actor: User, conversation_id: uuid.UUID, content: str
    ) -> tuple[Message, Message]:
        conversation = await self._get_owned(actor, conversation_id)
        history = self._build_history(await self.messages.list_by_conversation(conversation_id))

        user_message = await self.messages.add(
            Message(conversation_id=conversation.id, role=MessageRole.USER, content=content)
        )
        # The conversation id was not passed before, which quietly made escalation
        # impossible from the portal: the tools are withheld unless we can say whose ticket
        # it would be, and that answer starts from the conversation.
        reply = await self._reply(
            org_id=actor.org_id, history=history, content=content,
            conversation_id=conversation.id,
        )
        assistant_message = await self.messages.add(
            Message(
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content=reply.text,
                tool_trail=reply.tool_trail,
            )
        )
        await self.session.commit()
        return user_message, assistant_message

    # -- Device-initiated chat (Windows tray, no user login) -------------------

    async def device_chat(
        self, *, device: Device, content: str, conversation_id: uuid.UUID | None
    ) -> tuple[Conversation, Message, str]:
        """Handle a chat turn from a device's tray app, focused on that device.
        Returns (conversation, assistant_message, source)."""
        if conversation_id is not None:
            conversation = await self.conversations.get(conversation_id)
            if conversation is None or conversation.device_id != device.id:
                raise NotFoundError("Conversation not found")
            # Idle long enough and this is a new visit, not a continuation. Carrying the old
            # thread made the assistant answer the OLD problem: someone whose cache had been
            # cleared an hour earlier came back to ask about their time zone and was told
            # about the cache again. Enforced here rather than in the tray so it applies to
            # every agent version already in the field.
            if await self._has_gone_idle(conversation):
                conversation = await self._start_device_conversation(device)
        else:
            conversation = await self._start_device_conversation(device)

        # Gate on subscription: chat works only for a writable org (active plan or a
        # live trial). Suspended / past-due / canceled / expired-trial orgs get a
        # canned reply — no LLM call, no remediation.
        org = await self.orgs.get(device.org_id)
        if org is not None and not org_is_writable(org):
            await self.messages.add(
                Message(conversation_id=conversation.id, role=MessageRole.USER, content=content)
            )
            assistant_message = await self.messages.add(
                Message(
                    conversation_id=conversation.id,
                    role=MessageRole.ASSISTANT,
                    content=_SUBSCRIPTION_INACTIVE_REPLY,
                )
            )
            await self.session.commit()
            return conversation, assistant_message, "subscription_inactive"

        history = self._build_history(await self.messages.list_by_conversation(conversation.id))
        await self.messages.add(
            Message(conversation_id=conversation.id, role=MessageRole.USER, content=content)
        )

        # "What version are you?" — answer with this device's real agent version directly,
        # instead of the generic assistant reply.
        if _is_version_question(content):
            assistant_message = await self.messages.add(
                Message(
                    conversation_id=conversation.id,
                    role=MessageRole.ASSISTANT,
                    content=await self._version_reply(device),
                )
            )
            await self.session.commit()
            return conversation, assistant_message, "version"

        reply = await self._reply(
            org_id=device.org_id, history=history, content=content,
            device_hostname=device.hostname, acting_device_id=device.id,
            conversation_id=conversation.id,
        )
        assistant_message = await self.messages.add(
            Message(
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content=reply.text,
                tool_trail=reply.tool_trail,
            )
        )
        await self.session.commit()
        return conversation, assistant_message, reply.source

    async def device_history(
        self, *, device: Device
    ) -> tuple[uuid.UUID | None, list[tuple[str, str]]]:
        """The device's most recent conversation and its messages, so the tray can
        restore the chat when the user reopens it.

        Only while that conversation is still live. Past the idle window the window opens
        empty, which is the visible half of the rule device_chat enforces — restoring a
        transcript the next message would not continue would be worse than showing none.
        """
        conversation = await self.conversations.latest_for_device(device.id)
        if conversation is None or await self._has_gone_idle(conversation):
            return None, []
        messages = await self.messages.list_by_conversation(conversation.id)
        return conversation.id, [(m.role.value, m.content) for m in messages]

    async def _start_device_conversation(self, device: Device) -> Conversation:
        return await self.conversations.add(
            Conversation(
                org_id=device.org_id,
                device_id=device.id,
                title=f"{device.hostname} support",
            )
        )

    async def _has_gone_idle(self, conversation: Conversation) -> bool:
        """Whether nothing has been said in this conversation for the idle window.

        Measured from the last MESSAGE, not the conversation row: a long back-and-forth
        stays live as long as it is active, however old the thread itself is.
        """
        minutes = get_settings().device_chat_idle_minutes
        if minutes <= 0:
            return False   # an explicit opt-out: never reset
        messages = await self.messages.list_by_conversation(conversation.id)
        last_at = as_utc(messages[-1].created_at) if messages else as_utc(conversation.created_at)
        return last_at is not None and (utcnow() - last_at) > timedelta(minutes=minutes)

    async def _version_reply(self, device: Device) -> str:
        """A plain answer to 'what version are you?' — the device's real agent version, and
        whether a newer signed release is available (best-effort; never fails the reply)."""
        current = device.agent_version or "unknown"
        latest = None
        try:
            served = await AgentUpdateService(get_settings()).current()
            if served is not None:
                latest = json.loads(served[0]).get("version")
        except Exception:
            latest = None
        msg = f"I'm the ASTRA agent on {device.hostname}, running version {current}."
        if latest and current != "unknown":
            if latest == current:
                msg += " That's the latest release — you're up to date."
            else:
                msg += (
                    f" The latest release is {latest}, so an update is pending — it installs "
                    "automatically, usually within an hour."
                )
        return msg

    # -- Shared reply path: intent gate → semantic cache → cognitive engine ----

    async def _reply(
        self,
        *,
        org_id: uuid.UUID,
        history: list[dict[str, Any]],
        content: str,
        device_hostname: str | None = None,
        acting_device_id: uuid.UUID | None = None,
        conversation_id: uuid.UUID | None = None,
    ) -> Reply:
        settings = get_settings()

        # 0. An outstanding offer to raise a ticket owns this turn.
        #
        # Until now the only code that could answer one was the LLM's escalation tool, and
        # the real LLM runs only for ai_pro orgs — so on every other org ASTRA asked "shall
        # I raise a ticket?" after a failed fix, the user said yes, and nothing happened.
        # The offer sat open forever. Answering it here makes the question mean something
        # regardless of which provider is doing the talking.
        #
        # First, because a bare "yes please" put through the keyword rules is not a support
        # request and would be answered as if it were one.
        if conversation_id is not None:
            answered = await self._answer_pending_offer(
                org_id=org_id, conversation_id=conversation_id,
                device_id=acting_device_id, content=content,
            )
            if answered is not None:
                return answered

        # 1. Intent gate — reject clearly off-topic queries with no LLM call.
        if settings.ai_intent_gate_enabled and is_off_topic(content):
            return Reply(text=OFF_TOPIC_REPLY, tool_trail=None, source="intent_gate")

        # An actionable message (names an app, reports a problem, or asks for a cleanup)
        # must always reach the engine — a cached text answer must never shadow a fix.
        actionable = requires_live_action(content)

        # 2. Semantic cache — a repeated/near-duplicate general question is served free.
        if settings.ai_cache_enabled and not actionable:
            cached = await self.cache.lookup(org_id=org_id, query=content)
            if cached is not None:
                return Reply(text=cached, tool_trail=None, source="cache")

        # 3. The fix didn't help — move to the next tier rather than round the same loop.
        #
        # The built-in rules answer on keywords, so "outlook is still crashing" matches the
        # same rule that just failed and would restart Outlook a second time. What the
        # message actually means is that this tier is finished.
        force_llm = False
        ai_pro = bool(settings.anthropic_api_key) and await self._org_is_ai_pro(org_id)
        if conversation_id is not None and reports_still_broken(content):
            from app.services.support.attempts import attempts_in

            if await attempts_in(self.session, conversation_id):
                if ai_pro:
                    # Claude carries the escalation tools, so the ticket question stays its
                    # to ask. Two owners in one turn is two offers for one problem.
                    force_llm = True
                else:
                    offered = await self._offer_ticket(
                        org_id=org_id, conversation_id=conversation_id,
                        device_id=acting_device_id,
                    )
                    if offered is not None:
                        return offered

        # 4. Route the provider: a listed/common issue is free (built-in rules); a
        #    previously-learned fix is free (built-in path); only a genuinely new,
        #    unlisted problem is worth an LLM (Claude) call.
        provider, source = await self._route(
            org_id, content, device_hostname, force_llm=force_llm
        )

        # Nothing here can help and there is no model to ask. Answering with the built-in
        # greeting — "tell me what's going wrong and I'll take care of it" — to somebody who
        # has just told us what is going wrong is the worst of the available replies.
        #
        # `actionable` is the guard, and it is not decoration: without it "yes please" or
        # "thanks" reaches this branch too, and ASTRA offers to open a ticket about a
        # pleasantry. A ticket needs a complaint to be about.
        if (
            conversation_id is not None
            and actionable
            and isinstance(provider, StubProvider)
            and self._forced_provider is None
            and not StubProvider().can_handle(user_text=content, hostname=device_hostname)
        ):
            offered = await self._offer_ticket(
                org_id=org_id, conversation_id=conversation_id,
                device_id=acting_device_id, problem=content,
            )
            if offered is not None:
                return offered
        # Which assistant answers. Today there is one: the platform's built-in ASTRA
        # persona, seeded from the same constants the engine falls back to, so this changes
        # nothing until an operator publishes a different version. None — an unseeded
        # deployment — means the engine runs on the constants exactly as before.
        version = await AssistantService(self.session).published_builtin()
        result = await CognitiveEngine(self.session, provider=provider, version=version).run(
            org_id=org_id, history=history, user_message=content,
            device_hostname=device_hostname, acting_device_id=acting_device_id,
            conversation_id=conversation_id,
        )

        # 4. Mark the fixes as the model's, so the result path can tell them from the ones
        #    the built-in rules produced. Every task the assistant creates is stored as
        #    source=ASSISTANT either way, and by the time learning happens — minutes later,
        #    on the agent's result, in another request — which provider answered is no
        #    longer knowable from anything but the row.
        #
        #    Learning itself is NOT done here. A fix queued is not a fix that worked: the
        #    device has not run it yet, and remembering it now would auto-apply it forever
        #    on the strength of an intention. It is learned where the outcome arrives.
        if not isinstance(provider, (StubProvider, LearnedActionProvider)):
            task_ids = created_task_ids(result.tool_trail)
            if task_ids:
                await self.session.execute(
                    update(RemediationTask)
                    .where(RemediationTask.id.in_([uuid.UUID(t) for t in task_ids]))
                    .values(from_llm=True)
                )

        # 5. Cache only device-independent, non-actionable, successful answers.
        if (
            settings.ai_cache_enabled
            and not actionable
            and result.cacheable
            and not result.tool_trail
        ):
            await self.cache.store(org_id=org_id, query=content, answer=result.text)

        return Reply(text=result.text, tool_trail=result.tool_trail or None, source=source)

    async def _answer_pending_offer(
        self, *, org_id: uuid.UUID, conversation_id: uuid.UUID,
        device_id: uuid.UUID | None, content: str,
    ) -> Reply | None:
        """Treat this message as the answer to an outstanding "shall I raise a ticket?".

        Returns None when there is no offer open, or when the reply is neither a yes nor a
        no — in that case the user has moved on to something else and the message belongs to
        the normal path.

        The yes/no decision comes from EscalationService rather than from anything local:
        those patterns already carry the English and Hinglish forms people actually type,
        and a second copy would drift from the one the tool path uses.
        """
        from app.services.support import factory, requester
        from app.services.support.escalation import (
            ConsentMissing,
            EscalationService,
            classify_answer,
        )

        verdict = classify_answer(content)
        if verdict == "unclear":
            return None

        connector = await factory.build_connector(self.session, org_id)
        service = EscalationService(self.session, connector=connector)
        if await service.pending_offer(conversation_id) is None:
            return None

        if verdict == "no":
            await service.decline(conversation_id=conversation_id)
            await self.session.commit()
            return Reply(
                text="No problem — I won't raise a ticket. Tell me if you change your mind.",
                tool_trail=None, source="escalation",
            )

        settings = await factory.get_settings_for(self.session, org_id)
        offered = await service.pending_offer(conversation_id)
        category, sub_category = factory.category_for(
            settings, offered.action_id if offered else None
        )
        who = await requester.resolve(
            self.session, org_id=org_id, conversation_id=conversation_id, device_id=device_id
        )
        try:
            outcome = await service.raise_ticket(
                org_id=org_id, conversation_id=conversation_id,
                requester_email=who.email if who else None,
                category=category, sub_category=sub_category,
            )
        except ConsentMissing:
            # The service reads the FIRST reply after the offer, not the latest, so a "yes"
            # that follows some other remark is not consent to it. Committed because a
            # refusal closes the offer and that has to outlive the turn.
            await self.session.commit()
            return None
        await self.session.commit()
        return Reply(text=outcome.message, tool_trail=None, source="escalation")

    async def _offer_ticket(
        self, *, org_id: uuid.UUID, conversation_id: uuid.UUID,
        device_id: uuid.UUID | None, problem: str | None = None,
    ) -> Reply | None:
        """Ask whether to hand this to a human. None when we must not ask.

        The same conditions the model's tools are withheld under apply here: no helpdesk,
        no nameable requester, or an open ticket that already covers it. Asking and then
        failing is worse than never asking, because by then the user has stopped looking
        for a fix themselves.
        """
        from app.services.support import attempts, factory, requester
        from app.services.support.escalation import EscalationService

        connector = await factory.build_connector(self.session, org_id)
        if connector is None:
            return None
        who = await requester.resolve(
            self.session, org_id=org_id, conversation_id=conversation_id,
            device_id=device_id,
        )
        if who is None:
            return None

        dossier = await attempts.build_dossier(
            self.session, conversation_id=conversation_id, device_id=device_id,
            problem=problem,
        )
        if dossier is None:
            return None

        tried = await attempts.attempts_in(self.session, conversation_id)
        escalation, message = await EscalationService(
            self.session, connector=connector
        ).offer(
            org_id=org_id, conversation_id=conversation_id, device_id=device_id,
            user_id=who.user_id, dossier=dossier,
            action_id=tried[-1].action_id if tried else None,
        )
        await self.session.commit()
        # `escalation is None` means an open ticket already covers this; the message says
        # which one, and that is the right thing to send either way.
        return Reply(text=message, tool_trail=None, source="escalation")

    async def _route(
        self, org_id: uuid.UUID, content: str, device_hostname: str | None,
        *, force_llm: bool = False,
    ) -> tuple[LLMProvider, str]:
        """Pick who answers, cheapest capable first:
        1. An injected provider (tests) always wins.
        2. A listed/common issue → free built-in rules.
        3. A previously-learned fix for this kind of issue → free built-in path.
        4. Otherwise → the real LLM (Claude) — but only for Pro-AI orgs with a key set;
           Basic orgs stay on the built-in engine (its own memory/rules).
        The returned source string is recorded for cost telemetry."""
        if self._forced_provider is not None:
            return self._forced_provider, "engine"
        # The built-in rules already had their turn and the user says it did not help, so
        # skip them: running the same keyword match again would apply the same fix again.
        if force_llm:
            return get_provider(), "engine"
        if StubProvider().can_handle(user_text=content, hostname=device_hostname):
            return StubProvider(), "engine"
        fix = await self.learned.lookup(org_id=org_id, query=content)
        if fix is not None:
            return LearnedActionProvider(fix.action_id, fix.params), "learned"
        # Escalation to the real Claude LLM is a Pro-plan entitlement.
        if get_settings().anthropic_api_key and await self._org_is_ai_pro(org_id):
            return get_provider(), "engine"
        return StubProvider(), "engine"

    async def _org_is_ai_pro(self, org_id: uuid.UUID) -> bool:
        org = await self.session.get(Organization, org_id)
        return bool(org and org.ai_pro)

    async def _get_owned(self, actor: User, conversation_id: uuid.UUID) -> Conversation:
        conversation = await self.conversations.get(conversation_id)
        if conversation is None or conversation.user_id != actor.id:
            raise NotFoundError("Conversation not found")
        return conversation

    @staticmethod
    def _build_history(messages: list[Message]) -> list[dict[str, Any]]:
        # Prior user/assistant text turns in Anthropic wire format (tool turns are
        # re-derived fresh each turn, not replayed).
        return [{"role": m.role.value, "content": m.content} for m in messages]
