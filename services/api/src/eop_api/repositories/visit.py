from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from eop_api.models.visit import Visit
from eop_api.repositories.base import BaseRepository
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams, SearchParams

SEARCHABLE_FIELDS: Sequence[InstrumentedAttribute[Any]] = (Visit.notes,)
FILTERABLE_FIELDS: Mapping[str, InstrumentedAttribute[Any]] = {
    "employee_id": Visit.employee_id,
    "store_id": Visit.store_id,
}


class VisitRepository(BaseRepository[Visit]):
    """Data access layer for `Visit`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Visit)

    async def paginate(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        search: SearchParams | None = None,
        search_fields: Sequence[InstrumentedAttribute[Any]] = SEARCHABLE_FIELDS,
        filters: FilterParams | None = None,
        filterable_fields: Mapping[str, InstrumentedAttribute[Any]] | None = None,
    ) -> Page[Visit]:
        """Paginated listing, text-searched against `notes`.

        Filterable by `employee_id`/`store_id`.
        """
        return await super().paginate(
            offset=offset,
            limit=limit,
            search=search,
            search_fields=search_fields,
            filters=filters,
            filterable_fields=filterable_fields or FILTERABLE_FIELDS,
        )
