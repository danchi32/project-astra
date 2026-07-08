import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.conversations import (
    ConversationCreate,
    ConversationRead,
    MessageRead,
    SendMessageRequest,
    SendMessageResponse,
)
from app.services.conversations import ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post(
    "", response_model=ConversationRead, status_code=status.HTTP_201_CREATED,
    summary="Start a new AI conversation",
)
async def create_conversation(
    body: ConversationCreate,
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ConversationRead:
    conversation = await ConversationService(session).create(actor=actor, title=body.title)
    return ConversationRead.model_validate(conversation)


@router.get("", response_model=list[ConversationRead], summary="List your conversations")
async def list_conversations(
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[ConversationRead]:
    rows = await ConversationService(session).list_for_user(actor=actor)
    return [ConversationRead.model_validate(c) for c in rows]


@router.get(
    "/{conversation_id}/messages",
    response_model=list[MessageRead],
    summary="Get messages in a conversation",
)
async def get_messages(
    conversation_id: uuid.UUID,
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[MessageRead]:
    rows = await ConversationService(session).get_messages(
        actor=actor, conversation_id=conversation_id
    )
    return [MessageRead.model_validate(m) for m in rows]


@router.post(
    "/{conversation_id}/messages",
    response_model=SendMessageResponse,
    summary="Send a message and get the AI's reply",
)
async def send_message(
    conversation_id: uuid.UUID,
    body: SendMessageRequest,
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SendMessageResponse:
    user_msg, assistant_msg = await ConversationService(session).send_message(
        actor=actor, conversation_id=conversation_id, content=body.content
    )
    return SendMessageResponse(
        user_message=MessageRead.model_validate(user_msg),
        assistant_message=MessageRead.model_validate(assistant_msg),
    )
