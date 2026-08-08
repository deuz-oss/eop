import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eop_api.models.deduction import Deduction
from eop_api.repositories.base import BaseRepository


class DeductionRepository(BaseRepository[Deduction]):
    """Data access layer for `Deduction`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Deduction)

    async def list_by_employee_and_payroll_run(
        self, employee_id: uuid.UUID, payroll_run_id: uuid.UUID
    ) -> Sequence[Deduction]:
        """Every `Deduction` for `(employee_id, payroll_run_id)`. Consumed
        by `PayrollCalculationService.calculate` (D7) as
        `NON_STATUTORY_DEDUCTION` line items."""
        stmt = select(Deduction).where(
            Deduction.employee_id == employee_id, Deduction.payroll_run_id == payroll_run_id
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_by_employee(self, employee_id: uuid.UUID) -> Sequence[Deduction]:
        """Every `Deduction` for `employee_id`, across every payroll run.
        Used by the Owner-Only `GET /deductions` route."""
        stmt = select(Deduction).where(Deduction.employee_id == employee_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()
