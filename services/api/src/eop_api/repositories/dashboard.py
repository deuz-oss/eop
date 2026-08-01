from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from eop_api.models.assignment import Assignment
from eop_api.models.employee import Employee
from eop_api.models.organization import Organization
from eop_api.models.project import Project
from eop_api.models.task import Task


@dataclass(frozen=True)
class DashboardCounts:
    organizations: int
    projects: int
    employees: int
    assignments: int
    tasks: int


class DashboardRepository:
    """Read-only aggregate queries for dashboard statistics.

    Unlike the other repositories, this one is not tied to a single model, so
    it does not subclass `BaseRepository`. It never commits or rolls back.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_counts(self) -> DashboardCounts:
        """Total entity counts in a single round-trip via scalar subqueries."""
        stmt = select(
            select(func.count()).select_from(Organization).scalar_subquery().label("organizations"),
            select(func.count()).select_from(Project).scalar_subquery().label("projects"),
            select(func.count()).select_from(Employee).scalar_subquery().label("employees"),
            select(func.count()).select_from(Assignment).scalar_subquery().label("assignments"),
            select(func.count()).select_from(Task).scalar_subquery().label("tasks"),
        )
        result = await self.session.execute(stmt)
        row = result.one()
        return DashboardCounts(
            organizations=row.organizations,
            projects=row.projects,
            employees=row.employees,
            assignments=row.assignments,
            tasks=row.tasks,
        )

    async def count_tasks_by_status(self) -> dict[str, int]:
        stmt = select(Task.status, func.count()).group_by(Task.status)
        result = await self.session.execute(stmt)
        return dict(result.tuples().all())
