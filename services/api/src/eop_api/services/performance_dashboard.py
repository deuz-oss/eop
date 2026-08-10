from collections.abc import Callable

from eop_api.repositories.achievement import AchievementRepository
from eop_api.repositories.kpi import KpiRepository
from eop_api.repositories.target import TargetRepository
from eop_api.schemas.performance_dashboard import PerformanceDashboardResponse
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class PerformanceDashboardService:
    """Orchestrates read-only Performance Management summary counts. Never writes.

    Organization-wide counts only (`Kpi`/`Target`/`Achievement` row counts) --
    no Territory/Region scoping, no computed ratios/percentages/scoring
    (`docs/architecture/capabilities/dashboard/
    iteration-1-scope-and-implementation-plan.md` §4). Deliberately separate
    from the existing `DashboardService`/`DashboardRepository` (§3) -- that
    capability aggregates unrelated generic-entity scaffolding
    (`Organization`/`Project`/`Employee`/`Assignment`/`Task`), not the
    HR/Field Execution/Performance domain model.

    No repository of its own: `BaseRepository.count()` is already generic,
    so this service reads directly from `KpiRepository`/`TargetRepository`/
    `AchievementRepository`, mirroring `DashboardService`'s and
    `ReconciliationService`'s identical read-only-orchestration shape.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def get_summary(self) -> PerformanceDashboardResponse:
        async with self._uow_factory() as uow:
            kpi_count = await KpiRepository(uow.session).count()
            target_count = await TargetRepository(uow.session).count()
            achievement_count = await AchievementRepository(uow.session).count()
            return PerformanceDashboardResponse(
                kpi_count=kpi_count,
                target_count=target_count,
                achievement_count=achievement_count,
            )
