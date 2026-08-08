import uuid
from collections.abc import Callable

from eop_api.foundation.monetary.types import Money
from eop_api.models.payslip import Payslip
from eop_api.schemas.payslip import PayslipCreate
from eop_api.services.compensation import CompensationService
from eop_api.services.payslip import PayslipService
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class CompensationNotFoundError(Exception):
    """Raised when no Compensation exists for the employee being calculated."""


class CompensationInactiveError(Exception):
    """Raised when the employee's Compensation exists but `is_active` is False."""


class DuplicatePayslipError(Exception):
    """Raised when a Payslip already exists for the given employee and payroll run."""


class PayrollCalculationService:
    """Iteration 1 payroll computation: Gross Salary equals Net Salary.

    Domain-Service shaped, mirroring `ApprovalService`/`ReconciliationService`:
    owns no persisted data or table of its own. Reads through
    `CompensationService`, writes through `PayslipService` -- it does not
    reach into either service's own repository directly.

    Iteration 1 computation rule, owned here (not by `Payslip`, which never
    computes anything, per its own decision.md §4-5): Gross Salary is the
    employee's current active `Compensation.base_salary`; Net Salary equals
    Gross Salary exactly. No tax, BPJS, attendance, leave, overtime, loan,
    reimbursement, proration, or currency conversion is computed -- all are
    out of scope for Iteration 1 and explicitly deferred.

    A duplicate-`Payslip` check is performed before creation, but is not
    race-free (no unique constraint backs it at the database level, unlike
    e.g. `Compensation.employee_id`) -- accepted as a known limitation for
    Iteration 1, not a business requirement this document invents.
    """

    def __init__(
        self,
        compensation_service: CompensationService | None = None,
        payslip_service: PayslipService | None = None,
        uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork,
    ) -> None:
        self._compensation_service = compensation_service or CompensationService(uow_factory)
        self._payslip_service = payslip_service or PayslipService(uow_factory)

    async def calculate(self, payroll_run_id: uuid.UUID, employee_id: uuid.UUID) -> Payslip:
        compensation = await self._compensation_service.get_by_employee(employee_id)
        if compensation is None:
            raise CompensationNotFoundError(str(employee_id))
        if not compensation.is_active:
            raise CompensationInactiveError(str(employee_id))

        existing = await self._payslip_service.get_by_employee_and_payroll_run(
            employee_id, payroll_run_id
        )
        if existing is not None:
            raise DuplicatePayslipError(f"{employee_id}:{payroll_run_id}")

        salary = Money(compensation.base_salary_amount, compensation.base_salary_currency)

        return await self._payslip_service.create(
            PayslipCreate(
                employee_id=employee_id,
                payroll_run_id=payroll_run_id,
                gross_salary_amount=salary.amount,
                gross_salary_currency=salary.currency,
                net_salary_amount=salary.amount,
                net_salary_currency=salary.currency,
            )
        )
