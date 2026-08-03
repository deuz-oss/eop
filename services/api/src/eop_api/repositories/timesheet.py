import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from eop_api.models.timesheet import Timesheet
from eop_api.repositories.base import BaseRepository
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams, SearchParams

SEARCHABLE_FIELDS: Sequence[InstrumentedAttribute[Any]] = ()
FILTERABLE_FIELDS: Mapping[str, InstrumentedAttribute[Any]] = {
    "employee_id": Timesheet.employee_id,
    "status": Timesheet.status,
    "start_date": Timesheet.start_date,
    "end_date": Timesheet.end_date,
}


class TimesheetRepository(BaseRepository[Timesheet]):
    """Data access layer for `Timesheet`. Never commits or rolls back.

    Persistence only, scoped to the `timesheets` table -- per
    `docs/architecture/TIMESHEET_DESIGN.md` §6/§7, no projection queries and
    no joins against `AttendanceEvent`/`LeaveRequest`/`OvertimeRequest`/
    `Holiday`/`LeaveBalance` belong here.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Timesheet)

    async def get_by_employee(self, employee_id: uuid.UUID) -> Sequence[Timesheet]:
        stmt = select(Timesheet).where(Timesheet.employee_id == employee_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def paginate(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        search: SearchParams | None = None,
        search_fields: Sequence[InstrumentedAttribute[Any]] = SEARCHABLE_FIELDS,
        filters: FilterParams | None = None,
        filterable_fields: Mapping[str, InstrumentedAttribute[Any]] | None = None,
    ) -> Page[Timesheet]:
        """Paginated listing. Filterable by `employee_id`, `status`, `start_date`,
        and `end_date` (all equality)."""
        return await super().paginate(
            offset=offset,
            limit=limit,
            search=search,
            search_fields=search_fields,
            filters=filters,
            filterable_fields=filterable_fields or FILTERABLE_FIELDS,
        )
