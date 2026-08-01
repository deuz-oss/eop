import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eop_api.models.project import Project
from eop_api.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    """Data access layer for `Project`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Project)

    async def get_by_organization_and_code(
        self, organization_id: uuid.UUID, code: str
    ) -> Project | None:
        stmt = select(Project).where(
            Project.organization_id == organization_id,
            Project.code == code,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
