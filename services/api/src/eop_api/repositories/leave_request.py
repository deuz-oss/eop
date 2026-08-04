import uuid
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from eop_api.models.leave_request import LeaveRequest
from eop_api.repositories.base import BaseRepository
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams, SearchParams

SEARCHABLE_FIELDS: Sequence[InstrumentedAttribute[Any]] = (LeaveRequest.reason,)
FILTERABLE_FIELDS: Mapping[str, InstrumentedAttribute[Any]] = {
    "employee_id": LeaveRequest.employee_id,
    "status": LeaveRequest.status,
}


class LeaveRequestRepository(BaseRepository[LeaveRequest]):
    """Data access layer for `LeaveRequest`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, LeaveRequest)

    async def find_for_employee_on_date(
        self, employee_id: uuid.UUID, target_date: date
    ) -> Sequence[LeaveRequest]:
        """LeaveRequests covering `target_date` for `employee_id`, regardless of `status`.

        Single-table, same-model query only -- no join against any other
        aggregate, and no approval-status filtering: `status` is a business/
        workflow concept, not a persistence one, so interpreting it (e.g.
        "only `approved` counts") belongs entirely to the caller
        (`ReconciliationService`), per
        `docs/architecture/ATTENDANCE_RECONCILIATION_DESIGN.md` §5.
        """
        stmt = select(LeaveRequest).where(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.start_date <= target_date,
            LeaveRequest.end_date >= target_date,
        )
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
    ) -> Page[LeaveRequest]:
        """Paginated listing, text-searched against `reason`.

        Filterable by `employee_id` and `status`.
        """
        return await super().paginate(
            offset=offset,
            limit=limit,
            search=search,
            search_fields=search_fields,
            filters=filters,
            filterable_fields=filterable_fields or FILTERABLE_FIELDS,
        )
