import uuid
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from eop_api.models.work_schedule import WorkSchedule
from eop_api.repositories.base import BaseRepository
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams, SearchParams

FILTERABLE_FIELDS: Mapping[str, InstrumentedAttribute[Any]] = {
    "employee_id": WorkSchedule.employee_id,
    "shift_id": WorkSchedule.shift_id,
    "is_active": WorkSchedule.is_active,
}


class WorkScheduleRepository(BaseRepository[WorkSchedule]):
    """Data access layer for `WorkSchedule`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, WorkSchedule)

    async def list_by_employee_id(self, employee_id: uuid.UUID) -> Sequence[WorkSchedule]:
        """Every historical `WorkSchedule` row for `employee_id`, oldest first."""
        stmt = (
            select(WorkSchedule)
            .where(WorkSchedule.employee_id == employee_id)
            .order_by(WorkSchedule.effective_from)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_effective_as_of(
        self, employee_id: uuid.UUID, as_of_date: date
    ) -> Sequence[WorkSchedule]:
        """Every `WorkSchedule` row for `employee_id` effective on `as_of_date`.

        Persistence-only: may return more than one row (e.g. a correction and
        the row it corrects) -- resolving that down to one answer is
        `WorkScheduleService`'s job, mirroring
        `CompensationRepository.list_effective_as_of` exactly.
        """
        stmt = select(WorkSchedule).where(
            WorkSchedule.employee_id == employee_id,
            WorkSchedule.effective_from <= as_of_date,
            (WorkSchedule.effective_to.is_(None)) | (WorkSchedule.effective_to >= as_of_date),
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def find_overlapping_periods(
        self,
        employee_id: uuid.UUID,
        effective_from: date,
        effective_to: date | None,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> Sequence[WorkSchedule]:
        """Existing `WorkSchedule` rows for `employee_id` whose effective period
        overlaps [`effective_from`, `effective_to`], mirroring
        `CompensationRepository.find_overlapping_periods` exactly.
        """
        conditions = [
            WorkSchedule.employee_id == employee_id,
            WorkSchedule.effective_to.is_(None) | (WorkSchedule.effective_to >= effective_from),
        ]
        if effective_to is not None:
            conditions.append(WorkSchedule.effective_from <= effective_to)
        if exclude_id is not None:
            conditions.append(WorkSchedule.id != exclude_id)

        stmt = select(WorkSchedule).where(*conditions)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def paginate(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        search: SearchParams | None = None,
        search_fields: Sequence[InstrumentedAttribute[Any]] = (),
        filters: FilterParams | None = None,
        filterable_fields: Mapping[str, InstrumentedAttribute[Any]] | None = None,
    ) -> Page[WorkSchedule]:
        """Paginated listing, filterable by `employee_id`/`shift_id`/`is_active`."""
        return await super().paginate(
            offset=offset,
            limit=limit,
            search=search,
            search_fields=search_fields,
            filters=filters,
            filterable_fields=filterable_fields or FILTERABLE_FIELDS,
        )
