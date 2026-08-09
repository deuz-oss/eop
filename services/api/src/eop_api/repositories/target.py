import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from eop_api.models.target import Target
from eop_api.repositories.base import BaseRepository
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams, SearchParams

FILTERABLE_FIELDS: Mapping[str, InstrumentedAttribute[Any]] = {
    "employee_id": Target.employee_id,
    "kpi_id": Target.kpi_id,
    "period_year": Target.period_year,
    "period_month": Target.period_month,
}


class TargetRepository(BaseRepository[Target]):
    """Data access layer for `Target`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Target)

    async def get_by_identity(
        self, employee_id: uuid.UUID, kpi_id: uuid.UUID, period_year: int, period_month: int
    ) -> Target | None:
        stmt = select(Target).where(
            Target.employee_id == employee_id,
            Target.kpi_id == kpi_id,
            Target.period_year == period_year,
            Target.period_month == period_month,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def paginate(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        search: SearchParams | None = None,
        search_fields: Sequence[InstrumentedAttribute[Any]] = (),
        filters: FilterParams | None = None,
        filterable_fields: Mapping[str, InstrumentedAttribute[Any]] | None = None,
    ) -> Page[Target]:
        """Paginated listing, filterable by `employee_id`/`kpi_id`/
        `period_year`/`period_month`. No text-searchable field exists on
        `Target`."""
        return await super().paginate(
            offset=offset,
            limit=limit,
            search=search,
            search_fields=search_fields,
            filters=filters,
            filterable_fields=filterable_fields or FILTERABLE_FIELDS,
        )
