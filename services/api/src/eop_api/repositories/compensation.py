import uuid
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from eop_api.models.compensation import Compensation
from eop_api.repositories.base import BaseRepository
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams, SearchParams

FILTERABLE_FIELDS: Mapping[str, InstrumentedAttribute[Any]] = {
    "employee_id": Compensation.employee_id,
    "is_active": Compensation.is_active,
}


class CompensationRepository(BaseRepository[Compensation]):
    """Data access layer for `Compensation`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Compensation)

    async def list_by_employee_id(self, employee_id: uuid.UUID) -> Sequence[Compensation]:
        """Every historical `Compensation` row for `employee_id`, oldest first.

        Multiple rows per employee are expected
        (`docs/architecture/capabilities/compensation/decision.md` §17) --
        this does not assume or enforce at most one row.
        """
        stmt = (
            select(Compensation)
            .where(Compensation.employee_id == employee_id)
            .order_by(Compensation.effective_from)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_effective_as_of(
        self, employee_id: uuid.UUID, as_of_date: date
    ) -> Sequence[Compensation]:
        """Every `Compensation` row for `employee_id` effective on `as_of_date`.

        Persistence-only: returns every raw match, unresolved. Under
        normal operation (`decision.md` §19, O1) at most one row matches,
        but a correction row and the row it corrects (§19's overlap
        exemption) can both match by design -- resolving that down to one
        answer is `CompensationService`'s job (correction-precedence
        policy), not this repository's. Hand-written directly on this
        repository, mirroring `AttendanceEventRepository.exists_between`/
        `LeaveRequestRepository.find_for_employee_on_date` -- no generic
        `BaseRepository` range-query support exists or is added here
        (`effective-dating/decision.md` §3). Inclusive on both bounds,
        matching both of those existing precedents exactly. `is_active`
        plays no part in this predicate (`decision.md` §18, Option A3).
        """
        stmt = select(Compensation).where(
            Compensation.employee_id == employee_id,
            Compensation.effective_from <= as_of_date,
            (Compensation.effective_to.is_(None)) | (Compensation.effective_to >= as_of_date),
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
    ) -> Sequence[Compensation]:
        """Existing `Compensation` rows for `employee_id` whose effective period
        overlaps [`effective_from`, `effective_to`] (either bound may be open-ended).

        Persistence-only range-overlap query, extending `list_effective_as_of`'s
        same point-in-range predicate to a range-against-range comparison
        (`existing.effective_from <= requested_end` and
        `requested_start <= existing.effective_to`, both sides accounting
        for an open-ended `NULL`). `exclude_id` lets a correction row's
        overlap check omit the one row `decision.md` §19's exemption
        permits it to overlap -- this method does not decide *whether*
        that exemption applies; the caller (`CompensationService`) passes
        `exclude_id` only when it has already validated a correction
        target.
        """
        conditions = [
            Compensation.employee_id == employee_id,
            Compensation.effective_to.is_(None) | (Compensation.effective_to >= effective_from),
        ]
        if effective_to is not None:
            conditions.append(Compensation.effective_from <= effective_to)
        if exclude_id is not None:
            conditions.append(Compensation.id != exclude_id)

        stmt = select(Compensation).where(*conditions)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_active(self) -> Sequence[Compensation]:
        """Every `Compensation` row with `is_active=True`.

        Used only by `PayrollCalculationService`'s batch orchestration to
        determine the eligible-employee set for a `PayrollRun`, per
        `models/compensation.py`'s own documented purpose for `is_active`:
        "no longer considered by payroll processing" when `False`. No new
        eligibility rule is introduced here.
        """
        stmt = select(Compensation).where(Compensation.is_active.is_(True))
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
    ) -> Page[Compensation]:
        """Paginated listing, filterable by `employee_id`/`is_active`."""
        return await super().paginate(
            offset=offset,
            limit=limit,
            search=search,
            search_fields=search_fields,
            filters=filters,
            filterable_fields=filterable_fields or FILTERABLE_FIELDS,
        )
