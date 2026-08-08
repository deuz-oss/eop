import uuid
from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eop_api.models.allowance import Allowance
from eop_api.repositories.base import BaseRepository


class AllowanceRepository(BaseRepository[Allowance]):
    """Data access layer for `Allowance`. Never commits or rolls back.

    Mirrors `CompensationRepository` throughout, with every query
    additionally scoped (or not) by `allowance_type` per D6's "multiple
    simultaneous allowances" requirement -- overlap/correction/effective
    resolution partition by `(employee_id, allowance_type)`; batch
    consumption by `PayrollCalculationService` reads across all types at
    once.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Allowance)

    async def list_by_employee_id(self, employee_id: uuid.UUID) -> Sequence[Allowance]:
        stmt = (
            select(Allowance)
            .where(Allowance.employee_id == employee_id)
            .order_by(Allowance.allowance_type, Allowance.effective_from)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_effective_as_of(
        self, employee_id: uuid.UUID, allowance_type: str, as_of_date: date
    ) -> Sequence[Allowance]:
        """Every row for `(employee_id, allowance_type)` effective on
        `as_of_date`. Used by `AllowanceService.create`'s overlap check."""
        stmt = select(Allowance).where(
            Allowance.employee_id == employee_id,
            Allowance.allowance_type == allowance_type,
            Allowance.effective_from <= as_of_date,
            (Allowance.effective_to.is_(None)) | (Allowance.effective_to >= as_of_date),
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_effective_as_of_any_type(
        self, employee_id: uuid.UUID, as_of_date: date
    ) -> Sequence[Allowance]:
        """Every row for `employee_id`, across all `allowance_type`s,
        effective on `as_of_date`. Used by
        `AllowanceService.list_active_for_employee` (Payroll's read-only
        consumption, D6) -- an employee may hold multiple simultaneous
        allowances of different types."""
        stmt = select(Allowance).where(
            Allowance.employee_id == employee_id,
            Allowance.is_active.is_(True),
            Allowance.effective_from <= as_of_date,
            (Allowance.effective_to.is_(None)) | (Allowance.effective_to >= as_of_date),
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def find_overlapping_periods(
        self,
        employee_id: uuid.UUID,
        allowance_type: str,
        effective_from: date,
        effective_to: date | None,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> Sequence[Allowance]:
        """Existing rows for `(employee_id, allowance_type)` whose effective
        period overlaps `[effective_from, effective_to]`. Mirrors
        `CompensationRepository.find_overlapping_periods` exactly, with the
        added `allowance_type` scope."""
        conditions = [
            Allowance.employee_id == employee_id,
            Allowance.allowance_type == allowance_type,
            (Allowance.effective_to.is_(None)) | (Allowance.effective_to >= effective_from),
        ]
        if effective_to is not None:
            conditions.append(Allowance.effective_from <= effective_to)
        if exclude_id is not None:
            conditions.append(Allowance.id != exclude_id)

        stmt = select(Allowance).where(*conditions)
        result = await self.session.execute(stmt)
        return result.scalars().all()
