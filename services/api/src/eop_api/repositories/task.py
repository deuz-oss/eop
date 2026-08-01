import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eop_api.models.task import Task
from eop_api.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    """Data access layer for `Task`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Task)

    async def list_by_project(self, project_id: uuid.UUID) -> Sequence[Task]:
        stmt = select(Task).where(Task.project_id == project_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_by_assignee(self, assignee_id: uuid.UUID) -> Sequence[Task]:
        stmt = select(Task).where(Task.assignee_id == assignee_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()
