import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Conversation, Device, Message, MessageRole, User
from app.repositories.conversations import ConversationRepository, MessageRepository
from app.services.ai.cache import SemanticCache
from app.services.ai.cognitive import CognitiveEngine
from app.services.ai.intent import OFF_TOPIC_REPLY, is_off_topic, requires_live_action
from app.services.ai.provider import LLMProvider
from app.services.exceptions import NotFoundError


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
        # Provider is injectable so tests can pass a deterministic stub.
        self.engine = CognitiveEngine(session, provider=provider)
        self.cache = SemanticCache(session)

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

        history = self._build_history(await self.messages.list_by_conversation(conversation.id))
        await self.messages.add(
            Message(conversation_id=conversation.id, role=MessageRole.USER, content=content)
        )
        reply = await self._reply(
            org_id=device.org_id, history=history, content=content,
            device_hostname=device.hostname, acting_device_id=device.id,
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

    # -- Shared reply path: intent gate → semantic cache → cognitive engine ----

    async def _reply(
        self,
        *,
        org_id: uuid.UUID,
        history: list[dict[str, Any]],
        content: str,
        device_hostname: str | None = None,
        acting_device_id: uuid.UUID | None = None,
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

        # 3. Cognitive engine (the only path that costs an LLM call).
        result = await self.engine.run(
            org_id=org_id, history=history, user_message=content,
            device_hostname=device_hostname, acting_device_id=acting_device_id,
        )

        # 4. Cache only device-independent, non-actionable, successful answers.
        if (
            settings.ai_cache_enabled
            and not actionable
            and result.cacheable
            and not result.tool_trail
        ):
            await self.cache.store(org_id=org_id, query=content, answer=result.text)

        return Reply(text=result.text, tool_trail=result.tool_trail or None, source="engine")

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
