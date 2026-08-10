from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from eop_api.models.mission import Mission
from eop_api.repositories.base import BaseRepository
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams, SearchParams

FILTERABLE_FIELDS: Mapping[str, InstrumentedAttribute[Any]] = {
    "employee_id": Mission.employee_id,
    "store_id": Mission.store_id,
    "scheduled_date": Mission.scheduled_date,
}


class MissionRepository(BaseRepository[Mission]):
    """Data access layer for `Mission`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Mission)

    async def paginate(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        search: SearchParams | None = None,
        search_fields: Sequence[InstrumentedAttribute[Any]] = (),
        filters: FilterParams | None = None,
        filterable_fields: Mapping[str, InstrumentedAttribute[Any]] | None = None,
    ) -> Page[Mission]:
        """Paginated listing, filterable by `employee_id`/`store_id`/
        `scheduled_date`. No text-searchable field exists on `Mission`."""
        return await super().paginate(
            offset=offset,
            limit=limit,
            search=search,
            search_fields=search_fields,
            filters=filters,
            filterable_fields=filterable_fields or FILTERABLE_FIELDS,
        )
