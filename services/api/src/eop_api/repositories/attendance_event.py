from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from eop_api.models.attendance_event import AttendanceEvent
from eop_api.repositories.base import BaseRepository
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams, SearchParams

SEARCHABLE_FIELDS: Sequence[InstrumentedAttribute[Any]] = (AttendanceEvent.remarks,)
FILTERABLE_FIELDS: Mapping[str, InstrumentedAttribute[Any]] = {
    "employee_id": AttendanceEvent.employee_id,
    "shift_id": AttendanceEvent.shift_id,
    "event_type": AttendanceEvent.event_type,
    "source": AttendanceEvent.source,
}


class AttendanceEventRepository(BaseRepository[AttendanceEvent]):
    """Data access layer for `AttendanceEvent`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AttendanceEvent)

    async def paginate(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        search: SearchParams | None = None,
        search_fields: Sequence[InstrumentedAttribute[Any]] = SEARCHABLE_FIELDS,
        filters: FilterParams | None = None,
        filterable_fields: Mapping[str, InstrumentedAttribute[Any]] | None = None,
    ) -> Page[AttendanceEvent]:
        """Paginated listing, text-searched against `remarks`.

        Filterable by `employee_id`, `shift_id`, `event_type`, and `source`.
        """
        return await super().paginate(
            offset=offset,
            limit=limit,
            search=search,
            search_fields=search_fields,
            filters=filters,
            filterable_fields=filterable_fields or FILTERABLE_FIELDS,
        )
