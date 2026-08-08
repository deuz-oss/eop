import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eop_api.models.payslip import Payslip
from eop_api.repositories.base import BaseRepository


class PayslipRepository(BaseRepository[Payslip]):
    """Data access layer for `Payslip`. Never commits or rolls back.

    `create`/`get`/`list` only, inherited unmodified from `BaseRepository` --
    no `update`, `delete`, `paginate`, or search override, per
    `docs/architecture/capabilities/payslip/decision.md` §4-5.
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
