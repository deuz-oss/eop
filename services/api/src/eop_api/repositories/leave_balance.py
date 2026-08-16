import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from eop_api.models.leave_balance import LeaveBalance
from eop_api.repositories.base import BaseRepository
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams, SearchParams

SEARCHABLE_FIELDS: Sequence[InstrumentedAttribute[Any]] = ()
FILTERABLE_FIELDS: Mapping[str, InstrumentedAttribute[Any]] = {
    "employee_id": LeaveBalance.employee_id,
    "period_year": LeaveBalance.period_year,
}


class LeaveBalanceRepository(BaseRepository[LeaveBalance]):
    """Data access layer for `LeaveBalance`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, LeaveBalance)

    async def get_by_employee(self, employee_id: uuid.UUID) -> Sequence[LeaveBalance]:
        stmt = select(LeaveBalance).where(LeaveBalance.employee_id == employee_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_employee_and_period_year(
        self, employee_id: uuid.UUID, period_year: int
    ) -> Sequence[LeaveBalance]:
        """LeaveBalance rows for `employee_id` in `period_year`.

        Returns a sequence, not a single row: `(employee_id, period_year)` has
        no uniqueness constraint, so this cannot use `BaseRepository.get_by()`
        -- that helper's `scalar_one_or_none()` would raise `MultipleResultsFound`
        if more than one row matches. Interpreting 0/1/many matches belongs to
        the caller (`ApprovalService`), not this repository.
        """
        stmt = select(LeaveBalance).where(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.period_year == period_year,
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
    ) -> Page[LeaveBalance]:
        """Paginated listing. Filterable by `employee_id` and `period_year`."""
        return await super().paginate(
            offset=offset,
            limit=limit,
            search=search,
            search_fields=search_fields,
            filters=filters,
            filterable_fields=filterable_fields or FILTERABLE_FIELDS,
        )
