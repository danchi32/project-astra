import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Message, MessageRole, User
from app.repositories.conversations import ConversationRepository, MessageRepository
from app.services.ai.cognitive import CognitiveEngine
from app.services.ai.provider import LLMProvider
from app.services.exceptions import NotFoundError


class ConversationService:
    def __init__(self, session: AsyncSession, provider: LLMProvider | None = None) -> None:
        self.session = session
        self.conversations = ConversationRepository(session)
        self.messages = MessageRepository(session)
        # Provider is injectable so tests can pass a deterministic stub.
        self.engine = CognitiveEngine(session, provider=provider)

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

        result = await self.engine.run(
            org_id=actor.org_id, history=history, user_message=content
        )

        assistant_message = await self.messages.add(
            Message(
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content=result.text,
                tool_trail=result.tool_trail or None,
            )
        )
        await self.session.commit()
        return user_message, assistant_message

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
