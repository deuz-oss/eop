from collections.abc import Callable
from dataclasses import asdict

from eop_api.repositories.reporting import ReportingRepository
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.reporting import ReportingLineResponse
from eop_api.schemas.search import FilterParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class ReportingService:
    """Business logic for the Reporting operational report. Owns the
    transaction boundary via a UoW. Read-only: creates no data, per
    `docs/architecture/capabilities/performance/
    reporting-iteration-1-scope-and-implementation-plan.md`.

    Maps `ReportingRepository`'s repository-owned `ReportingRow` dataclass
    into `ReportingLineResponse` (the API schema) -- mirrors
    `DashboardService.get_stats()`'s identical `DashboardCounts` ->
    `DashboardResponse` mapping. `ReportingRepository` never returns an API
    schema directly.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def list_paginated(
        self, pagination: PaginationParams, filters: FilterParams | None = None
    ) -> Page[ReportingLineResponse]:
        async with self._uow_factory() as uow:
            repo = ReportingRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, filters=filters
            )
            return Page(
                items=[ReportingLineResponse(**asdict(row)) for row in page.items],
                total=page.total,
                offset=page.offset,
                limit=page.limit,
            )
