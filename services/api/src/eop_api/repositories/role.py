import uuid

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from eop_api.models.role import Role
from eop_api.models.user_role import user_roles
from eop_api.repositories.base import BaseRepository


class RoleRepository(BaseRepository[Role]):
    """Data access layer for `Role`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Role)

    async def get_by_name(self, name: str) -> Role | None:
        stmt = select(Role).where(Role.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def is_assigned(self, role_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        stmt = (
            select(user_roles.c.role_id)
            .where(user_roles.c.role_id == role_id, user_roles.c.user_id == user_id)
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.first() is not None

    async def assign_user(self, role_id: uuid.UUID, user_id: uuid.UUID) -> None:
        await self.session.execute(insert(user_roles).values(role_id=role_id, user_id=user_id))
        await self.session.flush()

    async def unassign_user(self, role_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        if not await self.is_assigned(role_id, user_id):
            return False

        stmt = delete(user_roles).where(
            user_roles.c.role_id == role_id, user_roles.c.user_id == user_id
        )
        await self.session.execute(stmt)
        await self.session.flush()
        return True

    async def get_role_names_for_user(self, user_id: uuid.UUID) -> set[str]:
        stmt = (
            select(Role.name)
            .join(user_roles, user_roles.c.role_id == Role.id)
            .where(user_roles.c.user_id == user_id)
        )
        result = await self.session.execute(stmt)
        return set(result.scalars().all())
