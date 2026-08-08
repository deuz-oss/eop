import uuid
from collections.abc import Callable, Sequence

from eop_api.foundation.monetary.types import Money
from eop_api.models.payslip import Payslip
from eop_api.schemas.payslip import PayslipCreate
from eop_api.services.compensation import CompensationService
from eop_api.services.payroll_run import PayrollRunService
from eop_api.services.payslip import PayrollRunNotFoundError, PayslipService
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
    `CompensationService`, writes through `PayslipService`, and (Iteration 2)
    drives `PayrollRun`'s lifecycle through `PayrollRunService` -- it does not
    reach into any of their repositories directly.

    Iteration 1/2 computation rule, owned here (not by `Payslip`, which never
    computes anything, per its own decision.md §4-5): Gross Salary is the
    employee's current active `Compensation.base_salary`; Net Salary equals
    Gross Salary exactly. No tax, BPJS, attendance, leave, overtime, loan,
    reimbursement, proration, or currency conversion is computed -- all remain
    out of scope, per `docs/architecture/capabilities/payroll/decision.md`
    Addendum (Version 2) §3.

    A duplicate-`Payslip` check is performed before creation, but is not
    race-free (no unique constraint backs it at the database level, unlike
    e.g. `Compensation.employee_id`) -- accepted as a known limitation, not a
    business requirement this document invents.
    """

    def __init__(
        self,
        compensation_service: CompensationService | None = None,
        payslip_service: PayslipService | None = None,
        payroll_run_service: PayrollRunService | None = None,
        uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork,
    ) -> None:
        self._compensation_service = compensation_service or CompensationService(uow_factory)
        self._payslip_service = payslip_service or PayslipService(uow_factory)
        self._payroll_run_service = payroll_run_service or PayrollRunService(uow_factory)

    async def calculate_batch(self, payroll_run_id: uuid.UUID) -> Sequence[Payslip]:
        """Processes every eligible employee for `payroll_run_id` as one batch.

        Per `docs/architecture/capabilities/payroll/decision.md` Addendum
        (Version 2) §1-2: `PayrollRun` is the batch boundary, not
        employee-scoped; this method orchestrates repeated calls to
        `calculate` rather than duplicating its computation logic.
        "Eligible" means "has an active `Compensation` row"
        (`CompensationService.list_active`) -- the only eligibility mechanism
        already supported by existing Payroll governance/code
        (`models/compensation.py`'s own documented purpose for `is_active`).

        Transitions the run `DRAFT -> PROCESSING` before processing and
        `PROCESSING -> COMPLETED` after -- raises
        `InvalidPayrollRunTransitionError` (via `PayrollRunService`) if the
        run is not currently `DRAFT`, which also prevents re-running an
        already-processed or in-progress run.

        An employee who already has a `Payslip` for this run (`calculate`
        raising `DuplicatePayslipError`) is skipped, not treated as a batch
        failure -- this is the existing per-employee duplicate protection,
        preserved rather than bypassed. Any other error from `calculate`
        propagates and aborts the batch.
        """
        if await self._payroll_run_service.get(payroll_run_id) is None:
            raise PayrollRunNotFoundError(str(payroll_run_id))

        await self._payroll_run_service.start_processing(payroll_run_id)

        eligible_compensations = await self._compensation_service.list_active()

        created: list[Payslip] = []
        for compensation in eligible_compensations:
            try:
                payslip = await self.calculate(payroll_run_id, compensation.employee_id)
            except DuplicatePayslipError:
                continue
            created.append(payslip)

        await self._payroll_run_service.complete(payroll_run_id)
        return created

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
