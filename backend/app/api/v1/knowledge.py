import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import User, UserRole
from app.schemas.knowledge import KnowledgeArticleCreate, KnowledgeArticleRead
from app.services.ai.knowledge import KnowledgeBaseService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

staff_required = require_roles(UserRole.ADMIN, UserRole.TECHNICIAN)


@router.get("", response_model=list[KnowledgeArticleRead], summary="List knowledge articles")
async def list_articles(
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[KnowledgeArticleRead]:
    rows = await KnowledgeBaseService(session).list_for_org(org_id=actor.org_id)
    return [KnowledgeArticleRead.model_validate(a) for a in rows]


@router.post(
    "", response_model=KnowledgeArticleRead, status_code=status.HTTP_201_CREATED,
    summary="Add a knowledge article (staff)",
)
async def create_article(
    body: KnowledgeArticleCreate,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> KnowledgeArticleRead:
    article = await KnowledgeBaseService(session).create(
        org_id=actor.org_id, title=body.title, content=body.content, actor_user_id=actor.id,
    )
    return KnowledgeArticleRead.model_validate(article)


@router.delete(
    "/{article_id}", status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a knowledge article (staff)",
)
async def delete_article(
    article_id: uuid.UUID,
    actor: User = Depends(staff_required),
    session: AsyncSession = Depends(get_db),
) -> None:
    await KnowledgeBaseService(session).delete(actor=actor, article_id=article_id)
