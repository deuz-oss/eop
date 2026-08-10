import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from eop_api.models.competitor_activity import CompetitorActivity
from eop_api.models.visit import Visit
from eop_api.repositories.base import BaseRepository
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams, SearchParams

FILTERABLE_FIELDS: Mapping[str, InstrumentedAttribute[Any]] = {
    "visit_id": CompetitorActivity.visit_id,
}


class CompetitorActivityRepository(BaseRepository[CompetitorActivity]):
    """Data access layer for `CompetitorActivity`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CompetitorActivity)

    async def list_by_visit_id(self, visit_id: uuid.UUID) -> Sequence[CompetitorActivity]:
        """All `CompetitorActivity` rows for one `Visit` -- a list, not a
        single optional row, since cardinality is many-per-Visit (unlike
        `Survey.get_by_visit_id`)."""
        stmt = select(CompetitorActivity).where(CompetitorActivity.visit_id == visit_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def paginate_by_employee_id(
        self, employee_id: uuid.UUID, *, offset: int = 0, limit: int = 50
    ) -> Page[CompetitorActivity]:
        """CompetitorActivity rows whose parent `Visit` belongs to
        `employee_id`, scoped at the SQL level via a join against `Visit`.

        Owner Only scoping cannot be expressed through the generic
        `FilterParams`/`filterable_fields` equality mechanism --
        `CompetitorActivity` carries no `employee_id` of its own by design
        -- so this is a narrow, hand-written query specific to this
        repository, mirroring `SurveyRepository.paginate_by_employee_id`
        exactly.
        """
        items_stmt = (
            select(CompetitorActivity)
            .join(Visit, CompetitorActivity.visit_id == Visit.id)
            .where(Visit.employee_id == employee_id)
            .offset(offset)
            .limit(limit)
        )
        items_result = await self.session.execute(items_stmt)
        items = list(items_result.scalars().all())

        count_stmt = (
            select(func.count())
            .select_from(CompetitorActivity)
            .join(Visit, CompetitorActivity.visit_id == Visit.id)
            .where(Visit.employee_id == employee_id)
        )
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar_one()

        return Page(items=items, total=total, offset=offset, limit=limit)

    async def paginate(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        search: SearchParams | None = None,
        search_fields: Sequence[InstrumentedAttribute[Any]] = (),
        filters: FilterParams | None = None,
        filterable_fields: Mapping[str, InstrumentedAttribute[Any]] | None = None,
    ) -> Page[CompetitorActivity]:
        """Paginated listing, filterable by `visit_id`."""
        return await super().paginate(
            offset=offset,
            limit=limit,
            search=search,
            search_fields=search_fields,
            filters=filters,
            filterable_fields=filterable_fields or FILTERABLE_FIELDS,
        )
