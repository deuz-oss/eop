import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from eop_api.models.achievement import Achievement
from eop_api.models.hr_employee import HrEmployee
from eop_api.models.kpi import Kpi
from eop_api.models.target import Target
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams

FILTERABLE_FIELDS: dict[str, InstrumentedAttribute[Any]] = {
    "employee_id": Target.employee_id,
    "kpi_id": Target.kpi_id,
    "period_year": Target.period_year,
    "period_month": Target.period_month,
}


@dataclass(frozen=True, slots=True)
class ReportingRow:
    """One `Achievement`, resolved through `Target` to `Kpi`/`HrEmployee`.

    Repository-owned, not the API response schema -- mirrors
    `DashboardRepository.get_counts()`'s own `DashboardCounts` dataclass
    precedent: the repository returns a plain, repository-local shape;
    mapping to `schemas.reporting.ReportingLineResponse` is
    `ReportingService`'s job, not this repository's.
    """

    achievement_id: uuid.UUID
    target_id: uuid.UUID
    kpi_id: uuid.UUID
    kpi_code: str
    kpi_name: str
    employee_id: uuid.UUID
    employee_number: str
    employee_full_name: str
    period_year: int
    period_month: int
    goal_value: Decimal
    actual_value: Decimal


class ReportingRepository:
    """Read-only, cross-aggregate query for the `Achievement -> Target ->
    Kpi + HrEmployee` operational report (`docs/architecture/capabilities/
    performance/reporting-iteration-1-scope-and-implementation-plan.md`).

    Unlike the other repositories, this one is not tied to a single model,
    so it does not subclass `BaseRepository` -- mirrors `DashboardRepository`'s
    own identical exception, for the same reason: a 4-table join is not any
    one aggregate's own persistence concern. Never commits or rolls back.

    One row per existing `Achievement` -- a `Target` with no recorded
    `Achievement` never appears (`ON DELETE RESTRICT` on
    `Achievement.target_id` guarantees every `Achievement` resolves a
    `Target`, `Kpi`, and `HrEmployee`, so no left-join/null-handling case
    exists).
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _base_query(self) -> Any:
        return (
            select(
                Achievement.id.label("achievement_id"),
                Target.id.label("target_id"),
                Kpi.id.label("kpi_id"),
                Kpi.code.label("kpi_code"),
                Kpi.name.label("kpi_name"),
                HrEmployee.id.label("employee_id"),
                HrEmployee.employee_number.label("employee_number"),
                HrEmployee.full_name.label("employee_full_name"),
                Target.period_year.label("period_year"),
                Target.period_month.label("period_month"),
                Target.goal_value.label("goal_value"),
                Achievement.actual_value.label("actual_value"),
            )
            .join(Target, Achievement.target_id == Target.id)
            .join(Kpi, Target.kpi_id == Kpi.id)
            .join(HrEmployee, Target.employee_id == HrEmployee.id)
        )

    def _apply_filters(self, stmt: Any, filters: FilterParams | None) -> Any:
        if filters is None:
            return stmt
        for field_name, value in filters.values.items():
            column = FILTERABLE_FIELDS.get(field_name)
            if column is not None:
                stmt = stmt.where(column == value)
        return stmt

    async def paginate(
        self, *, offset: int = 0, limit: int = 50, filters: FilterParams | None = None
    ) -> Page[ReportingRow]:
        filtered_stmt = self._apply_filters(self._base_query(), filters)

        items_stmt = filtered_stmt.offset(offset).limit(limit)
        items_result = await self.session.execute(items_stmt)
        items = [ReportingRow(**row._mapping) for row in items_result.all()]

        # Filters are already applied inside `filtered_stmt` -- wrapping it as a
        # subquery and counting its rows avoids re-applying (and mismatching)
        # the same WHERE conditions against a differently-scoped count query,
        # which `BaseRepository.paginate`'s single-table shape does not need to
        # guard against.
        count_stmt = select(func.count()).select_from(filtered_stmt.subquery())
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar_one()

        return Page(items=items, total=total, offset=offset, limit=limit)
