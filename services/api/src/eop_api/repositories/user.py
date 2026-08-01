from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eop_api.models.user import User
from eop_api.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Data access layer for `User`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, User)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
