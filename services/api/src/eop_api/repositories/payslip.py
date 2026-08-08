import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eop_api.models.payslip import Payslip
from eop_api.repositories.base import BaseRepository


class PayslipRepository(BaseRepository[Payslip]):
    """Data access layer for `Payslip`. Never commits or rolls back.

    `create`/`get`/`list` only, inherited unmodified from `BaseRepository` --
    no `update`, `paginate`, or search override, per
    `docs/architecture/capabilities/payslip/decision.md` §4-5. `delete` is
    inherited but is used only by `PayslipService.delete_by_payroll_run`'s
    internal, completion-gated rerun path (E5/D9,
    `implementation-plan.md` §3.3) -- never by any API route.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Payslip)

    async def get_by_employee_and_payroll_run(
        self, employee_id: uuid.UUID, payroll_run_id: uuid.UUID
    ) -> Payslip | None:
        """Whether a `Payslip` already exists for this employee/payroll run pair.

        Single-table, same-model query only -- used by `PayrollCalculationService`
        to avoid computing a duplicate `Payslip` for the same run.
        """
        stmt = select(Payslip).where(
            Payslip.employee_id == employee_id, Payslip.payroll_run_id == payroll_run_id
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_payroll_run(self, payroll_run_id: uuid.UUID) -> Sequence[Payslip]:
        """Every `Payslip` for `payroll_run_id`. Used only by
        `PayslipService.delete_by_payroll_run`'s internal rerun path."""
        stmt = select(Payslip).where(Payslip.payroll_run_id == payroll_run_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()
