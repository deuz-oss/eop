from collections.abc import Callable

from eop_api.repositories.dashboard import DashboardRepository
from eop_api.schemas.dashboard import DashboardResponse
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class DashboardService:
    """Orchestrates read-only dashboard aggregate queries. Never writes."""

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def get_stats(self) -> DashboardResponse:
        async with self._uow_factory() as uow:
            repo = DashboardRepository(uow.session)
            counts = await repo.get_counts()
            tasks_by_status = await repo.count_tasks_by_status()
            return DashboardResponse(
                organizations=counts.organizations,
                projects=counts.projects,
                employees=counts.employees,
                assignments=counts.assignments,
                tasks=counts.tasks,
                tasks_by_status=tasks_by_status,
            )
