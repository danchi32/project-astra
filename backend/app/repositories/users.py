import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def list_by_org(self, org_id: uuid.UUID) -> list[User]:
        result = await self.session.execute(
            select(User).where(User.org_id == org_id).order_by(User.created_at)
        )
        return list(result.scalars().all())

    async def list_page(
        self, org_id: uuid.UUID, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[User], int]:
        from app.schemas.pagination import paginate

        stmt = select(User).where(User.org_id == org_id).order_by(User.created_at)
        rows, total, _, _ = await paginate(
            self.session, stmt, page=offset // max(1, limit) + 1, page_size=limit
        )
        return rows, total

    async def emails_for(
        self, org_id: uuid.UUID, user_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, str]:
        """Emails for just the users referenced by the rows being rendered.

        Labelling one page of audit entries used to load every user in the org — fine at ten
        users, a second table scan per page view at two thousand.
        """
        if not user_ids:
            return {}
        result = await self.session.execute(
            select(User.id, User.email).where(
                User.org_id == org_id, User.id.in_(user_ids)
            )
        )
        return {row[0]: row[1] for row in result.all()}

    async def add(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def delete(self, user: User) -> None:
        await self.session.delete(user)
