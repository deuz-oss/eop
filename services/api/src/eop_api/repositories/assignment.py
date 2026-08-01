import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eop_api.models.assignment import Assignment
from eop_api.repositories.base import BaseRepository


class AssignmentRepository(BaseRepository[Assignment]):
    """Data access layer for `Assignment`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Assignment)

    async def get_by_employee_and_project(
        self, employee_id: uuid.UUID, project_id: uuid.UUID
    ) -> Assignment | None:
        stmt = select(Assignment).where(
            Assignment.employee_id == employee_id,
            Assignment.project_id == project_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
