from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from eop_api.models.holiday import Holiday
from eop_api.repositories.base import BaseRepository
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams, SearchParams

SEARCHABLE_FIELDS: Sequence[InstrumentedAttribute[Any]] = (Holiday.code, Holiday.name)
FILTERABLE_FIELDS: Mapping[str, InstrumentedAttribute[Any]] = {"holiday_date": Holiday.holiday_date}


class HolidayRepository(BaseRepository[Holiday]):
    """Data access layer for `Holiday`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Holiday)

    async def get_by_code(self, code: str) -> Holiday | None:
        return await self.get_by(Holiday.code, code)

    async def get_by_holiday_date(self, holiday_date: date) -> Holiday | None:
        return await self.get_by(Holiday.holiday_date, holiday_date)

    async def paginate(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        search: SearchParams | None = None,
        search_fields: Sequence[InstrumentedAttribute[Any]] = SEARCHABLE_FIELDS,
        filters: FilterParams | None = None,
        filterable_fields: Mapping[str, InstrumentedAttribute[Any]] | None = FILTERABLE_FIELDS,
    ) -> Page[Holiday]:
        """Paginated listing, text-searched against `code`/`name`, filterable by `holiday_date`."""
        return await super().paginate(
            offset=offset,
            limit=limit,
            search=search,
            search_fields=search_fields,
            filters=filters,
            filterable_fields=filterable_fields,
        )
