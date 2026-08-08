from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eop_api.models.payroll_statutory_parameter import PayrollStatutoryParameter
from eop_api.repositories.base import BaseRepository


class PayrollStatutoryParameterRepository(BaseRepository[PayrollStatutoryParameter]):
    """Data access layer for `PayrollStatutoryParameter`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, PayrollStatutoryParameter)

    async def list_effective_as_of(
        self, key: str, as_of_date: date
    ) -> Sequence[PayrollStatutoryParameter]:
        """Every row for `key` effective on `as_of_date`. Mirrors
        `CompensationRepository.list_effective_as_of` exactly, scoped by
        `key` instead of `employee_id`. Persistence-only: returns every raw
        match, unresolved -- `PayrollStatutoryParameterService.get_value`
        resolves via `EffectiveDatingEvaluator`."""
        stmt = select(PayrollStatutoryParameter).where(
            PayrollStatutoryParameter.key == key,
            PayrollStatutoryParameter.effective_from <= as_of_date,
            (PayrollStatutoryParameter.effective_to.is_(None))
            | (PayrollStatutoryParameter.effective_to >= as_of_date),
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def find_overlapping_periods(
        self,
        key: str,
        effective_from: date,
        effective_to: date | None,
    ) -> Sequence[PayrollStatutoryParameter]:
        """Existing rows for `key` whose effective period overlaps
        `[effective_from, effective_to]` (open-ended if `None`). Mirrors
        `CompensationRepository.find_overlapping_periods`; no correction
        concept exists for parameters, so there is no `exclude_id`."""
        conditions = [
            PayrollStatutoryParameter.key == key,
            (PayrollStatutoryParameter.effective_to.is_(None))
            | (PayrollStatutoryParameter.effective_to >= effective_from),
        ]
        if effective_to is not None:
            conditions.append(PayrollStatutoryParameter.effective_from <= effective_to)

        stmt = select(PayrollStatutoryParameter).where(*conditions)
        result = await self.session.execute(stmt)
        return result.scalars().all()
