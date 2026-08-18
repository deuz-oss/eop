import uuid
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from eop_api.models.payroll_run import PayrollRun
from eop_api.repositories.base import BaseRepository
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams, SearchParams

SEARCHABLE_FIELDS: Sequence[InstrumentedAttribute[Any]] = (PayrollRun.code, PayrollRun.name)


class PayrollRunRepository(BaseRepository[PayrollRun]):
    """Data access layer for `PayrollRun`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, PayrollRun)

    async def get_by_code(self, code: str) -> PayrollRun | None:
        stmt = select(PayrollRun).where(PayrollRun.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_overlapping_period(
        self,
        currency: str,
        period_start: date,
        period_end: date,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> Sequence[PayrollRun]:
        """Existing `PayrollRun` rows for `currency` whose period overlaps
        `[period_start, period_end]`. Implements D8/E7 (one currency per
        `PayrollRun`, segmented by currency): two runs for the same period
        may coexist only if their currencies differ. Mirrors
        `CompensationRepository.find_overlapping_periods`'s range-overlap
        shape (`period_start`/`period_end` are never open-ended here, unlike
        Compensation's `effective_to`, since D1 fixes every `PayrollRun` to
        exactly one calendar month)."""
        stmt = select(PayrollRun).where(
            PayrollRun.currency == currency,
            PayrollRun.period_start <= period_end,
            PayrollRun.period_end >= period_start,
        )
        if exclude_id is not None:
            stmt = stmt.where(PayrollRun.id != exclude_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def find_covering_date(self, target_date: date) -> Sequence[PayrollRun]:
        """Existing `PayrollRun` rows (any `currency`, any `status`) whose
        `period_start`/`period_end` covers `target_date`.

        Persistence-only: returns every raw match, unresolved -- interpreting
        `status` (e.g. rejecting a lock check only when a match is not
        `DRAFT`) is the caller's job (`AttendanceEventService`), not this
        repository's. Rows with `period_start`/`period_end` still `NULL`
        (the pre-Iteration-2 historical gap noted on the model) never match,
        since a `NULL` bound cannot cover any date. Mirrors
        `find_overlapping_period`'s range shape, without the `currency`
        segmentation that method's own overlap rule needs -- an attendance
        event's lock boundary does not depend on `PayrollRun.currency`.
        """
        stmt = select(PayrollRun).where(
            PayrollRun.period_start.is_not(None),
            PayrollRun.period_end.is_not(None),
            PayrollRun.period_start <= target_date,
            PayrollRun.period_end >= target_date,
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
    ) -> Page[PayrollRun]:
        """Paginated listing, text-searched against `code`/`name`."""
        return await super().paginate(
            offset=offset,
            limit=limit,
            search=search,
            search_fields=search_fields,
            filters=filters,
            filterable_fields=filterable_fields,
        )
