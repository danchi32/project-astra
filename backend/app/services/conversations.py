import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Conversation, Device, Message, MessageRole, Organization, User
from app.repositories.conversations import ConversationRepository, MessageRepository
from app.repositories.organizations import OrganizationRepository
from app.services.ai.cache import SemanticCache
from app.services.ai.cognitive import CognitiveEngine
from app.services.ai.intent import OFF_TOPIC_REPLY, is_off_topic, requires_live_action
from app.services.ai.learned import LearnedFixStore, learnable_action
from app.services.ai.provider import (
    LearnedActionProvider,
    LLMProvider,
    StubProvider,
    get_provider,
)
from app.services.agent_update import AgentUpdateService
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
        reply = await self._reply(org_id=actor.org_id, history=history, content=content)
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
        else:
            conversation = await self.conversations.add(
                Conversation(
                    org_id=device.org_id,
                    device_id=device.id,
                    title=f"{device.hostname} support",
                )
            )

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
        restore the chat when the user reopens it."""
        conversation = await self.conversations.latest_for_device(device.id)
        if conversation is None:
            return None, []
        messages = await self.messages.list_by_conversation(conversation.id)
        return conversation.id, [(m.role.value, m.content) for m in messages]

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

        # 3. Route the provider: a listed/common issue is free (built-in rules); a
        #    previously-learned fix is free (built-in path); only a genuinely new,
        #    unlisted problem is worth an LLM (Claude) call.
        provider, source = await self._route(org_id, content, device_hostname)
        result = await CognitiveEngine(self.session, provider=provider).run(
            org_id=org_id, history=history, user_message=content,
            device_hostname=device_hostname, acting_device_id=acting_device_id,
            conversation_id=conversation_id,
        )

        # 4. Learn: if a NON-built-in provider (the LLM) solved a new issue by
        #    applying a fix, remember it so the same kind of issue is handled for
        #    free next time. Built-in and already-learned paths teach nothing new.
        if not isinstance(provider, (StubProvider, LearnedActionProvider)):
            learned = learnable_action(result.tool_trail)
            if learned is not None:
                await self.learned.learn(
                    org_id=org_id, query=content, action_id=learned[0], params=learned[1]
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

    async def _route(
        self, org_id: uuid.UUID, content: str, device_hostname: str | None
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
