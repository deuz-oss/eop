import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from eop_api.models.survey import Survey
from eop_api.models.visit import Visit
from eop_api.repositories.base import BaseRepository
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams, SearchParams

FILTERABLE_FIELDS: Mapping[str, InstrumentedAttribute[Any]] = {"visit_id": Survey.visit_id}


class SurveyRepository(BaseRepository[Survey]):
    """Data access layer for `Survey`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Survey)

    async def get_by_visit_id(self, visit_id: uuid.UUID) -> Survey | None:
        stmt = select(Survey).where(Survey.visit_id == visit_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def paginate_by_employee_id(
        self, employee_id: uuid.UUID, *, offset: int = 0, limit: int = 50
    ) -> Page[Survey]:
        """Surveys whose parent `Visit` belongs to `employee_id`, scoped at
        the SQL level via a join against `Visit`.

        Owner Only scoping cannot be expressed through the generic
        `FilterParams`/`filterable_fields` equality mechanism -- `Survey`
        carries no `employee_id` of its own by design (`iteration-1-scope-
        and-implementation-plan.md` §5) -- so this is a narrow, hand-written
        query specific to this repository, not a `BaseRepository` change.
        """
        items_stmt = (
            select(Survey)
            .join(Visit, Survey.visit_id == Visit.id)
            .where(Visit.employee_id == employee_id)
            .offset(offset)
            .limit(limit)
        )
        items_result = await self.session.execute(items_stmt)
        items = list(items_result.scalars().all())

        count_stmt = (
            select(func.count())
            .select_from(Survey)
            .join(Visit, Survey.visit_id == Visit.id)
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
    ) -> Page[Survey]:
        """Paginated listing, filterable by `visit_id`. No text-searchable
        field exists on `Survey` (three booleans only)."""
        return await super().paginate(
            offset=offset,
            limit=limit,
            search=search,
            search_fields=search_fields,
            filters=filters,
            filterable_fields=filterable_fields or FILTERABLE_FIELDS,
        )
