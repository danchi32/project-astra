import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Message


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, conversation_id: uuid.UUID) -> Conversation | None:
        return await self.session.get(Conversation, conversation_id)

    async def list_by_user(self, user_id: uuid.UUID) -> list[Conversation]:
        result = await self.session.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.created_at.desc())
        )
        return list(result.scalars().all())

    async def add(self, conversation: Conversation) -> Conversation:
        self.session.add(conversation)
        await self.session.flush()
        return conversation


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_conversation(self, conversation_id: uuid.UUID) -> list[Message]:
        result = await self.session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        return list(result.scalars().all())

    async def add(self, message: Message) -> Message:
        self.session.add(message)
        await self.session.flush()
        return message
