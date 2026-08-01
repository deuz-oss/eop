from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eop_api.models.employee import Employee
from eop_api.repositories.base import BaseRepository


class EmployeeRepository(BaseRepository[Employee]):
    """Data access layer for `Employee`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Employee)

    async def get_by_email(self, email: str) -> Employee | None:
        stmt = select(Employee).where(Employee.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
