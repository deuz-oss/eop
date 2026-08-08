import uuid
from collections.abc import Callable, Sequence
from datetime import date
from decimal import Decimal

from eop_api.core.payroll import (
    DEDUCTION_LINE_ITEM_TYPES,
    EARNING_LINE_ITEM_TYPES,
    PayrollRunStatus,
    PayslipLineItemType,
)
from eop_api.foundation.monetary.types import Money
from eop_api.models.payroll_run import PayrollRun
from eop_api.models.payslip import Payslip
from eop_api.schemas.payslip import PayslipCreate
from eop_api.schemas.payslip_line_item import PayslipLineItemCreate
from eop_api.services.allowance import AllowanceService
from eop_api.services.compensation import CompensationService
from eop_api.services.deduction import DeductionService
from eop_api.services.payroll.attendance_leave_deduction_calculator import (
    AttendanceLeaveDeductionCalculator,
)
from eop_api.services.payroll.overtime_calculator import OvertimeCalculator
from eop_api.services.payroll.rate_resolver import PayrollRateResolver
from eop_api.services.payroll.statutory_tax_calculator import StatutoryTaxCalculator
from eop_api.services.payroll_run import PayrollRunService
from eop_api.services.payroll_statutory_parameter import PayrollStatutoryParameterService
from eop_api.services.payslip import PayrollRunNotFoundError, PayslipService
from eop_api.services.reconciliation import ReconciliationService
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class CompensationNotFoundError(Exception):
    """Raised when no Compensation exists for the employee being calculated."""


class CompensationInactiveError(Exception):
    """Raised when the employee's Compensation exists but `is_active` is False."""


class CompensationCurrencyMismatchError(Exception):
    """Raised when an employee's effective Compensation currency does not
    match the `PayrollRun`'s own currency (D8/E7: one currency per
    `PayrollRun`)."""


class PayrollRunAlreadyCompletedError(Exception):
    """Raised when `calculate`/`calculate_batch` is attempted against a
    `COMPLETED` `PayrollRun` (E5: immutable completed results)."""


class PayrollRunMissingPeriodError(Exception):
    """Raised when `calculate`/`calculate_batch` is attempted against a
    `PayrollRun` that predates Advanced Payroll and has no
    `period_start`/`period_end`/`currency` (Iteration 1-3 rows; these three
    columns are nullable only for that historical-compatibility reason,
    `models/payroll_run.py`). Such a run cannot be computed by Advanced
    Payroll -- it must be recreated with a period/currency, per
    `PayrollRunCreate`."""


class DuplicatePayslipError(Exception):
    """Raised when a Payslip already exists for the given employee and payroll run."""


class PayrollCalculationService:
    """Advanced Payroll's calculation entry point (E1/E2/E8).

    Domain-Service shaped, mirroring `ApprovalService`/`ReconciliationService`:
    owns no persisted data or table of its own. Composes four small
    calculation components (`PayrollRateResolver`, `OvertimeCalculator`,
    `AttendanceLeaveDeductionCalculator`, `StatutoryTaxCalculator`) via
    constructor injection -- plain composition, not a rule/plugin framework
    (E8). Reads through `CompensationService`/`AllowanceService`/
    `DeductionService`, writes through `PayslipService`, drives
    `PayrollRun`'s lifecycle through `PayrollRunService` -- it does not
    reach into any of their repositories directly. Execution remains
    synchronous/request-driven throughout (E2) -- no background job/event
    infrastructure is introduced.

    Builds a structured result (E1): every earning/deduction is a
    `PayslipLineItem`, classified by `PayslipLineItemType` via
    `EARNING_LINE_ITEM_TYPES`/`DEDUCTION_LINE_ITEM_TYPES` (`core/payroll.py`)
    -- never by the sign of an amount, which is always stored unsigned.
    `gross = sum(earning line items)`, `net = gross - sum(deduction line
    items)`.

    `Compensation` is resolved via `CompensationService.get_by_employee(...,
    as_of_date=payroll_run.period_end)` -- Compensation's own, already-
    tested `EffectiveDatingEvaluator` + correction-precedence resolution
    (`decision.md` §18-19), never re-implemented here. `is_active` is
    consulted only as Payroll's own eligibility flag (unchanged from
    Iteration 1-3), never as a temporal-validity signal -- resolving "the
    effective row" is entirely Compensation's own as-of-date mechanism.

    Currency enforcement (D8/E7): a Compensation whose currency does not
    match `payroll_run.currency` is excluded from batch eligibility and
    rejected outright by `calculate`.

    Rerun (D9/E5): `calculate_batch` clears any existing Payslips for the
    run via `PayslipService.delete_by_payroll_run` before recomputing --
    safe and idempotent while the run is `DRAFT`/`PROCESSING`; both
    `calculate`/`calculate_batch` reject outright once the run is
    `COMPLETED`. This also resolves the Iteration-1-3 "stuck in
    PROCESSING" gap: a batch that fails partway (e.g. one employee's data
    is genuinely ambiguous) leaves the run in `PROCESSING` with partial
    Payslips; a subsequent `calculate_batch` call clears them and starts
    over, rather than being permanently unrecoverable.
    """

    def __init__(
        self,
        compensation_service: CompensationService | None = None,
        allowance_service: AllowanceService | None = None,
        deduction_service: DeductionService | None = None,
        payslip_service: PayslipService | None = None,
        payroll_run_service: PayrollRunService | None = None,
        rate_resolver: PayrollRateResolver | None = None,
        overtime_calculator: OvertimeCalculator | None = None,
        attendance_leave_deduction_calculator: AttendanceLeaveDeductionCalculator | None = None,
        statutory_tax_calculator: StatutoryTaxCalculator | None = None,
        uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork,
    ) -> None:
        self._compensation_service = compensation_service or CompensationService(uow_factory)
        self._allowance_service = allowance_service or AllowanceService(uow_factory)
        self._deduction_service = deduction_service or DeductionService(uow_factory)
        self._payslip_service = payslip_service or PayslipService(uow_factory)
        self._payroll_run_service = payroll_run_service or PayrollRunService(uow_factory)

        # Every calculator shares one `uow_factory`-wired `PayrollStatutoryParameterService`
        # instance (not each defaulting to its own) -- otherwise a caller supplying a
        # non-default `uow_factory` (e.g. tests, each on an isolated engine) would silently
        # leave the calculators reading/writing the *application's own default* database
        # instead, since `PayrollStatutoryParameterService()`'s own default falls back to
        # `SQLAlchemyUnitOfWork`'s default `AsyncSessionLocal`, not this instance's `uow_factory`.
        parameter_service = PayrollStatutoryParameterService(uow_factory)
        self._rate_resolver = rate_resolver or PayrollRateResolver(parameter_service)
        self._overtime_calculator = overtime_calculator or OvertimeCalculator(
            self._rate_resolver, parameter_service, uow_factory
        )
        self._attendance_leave_deduction_calculator = (
            attendance_leave_deduction_calculator
            or AttendanceLeaveDeductionCalculator(
                self._rate_resolver, ReconciliationService(uow_factory)
            )
        )
        self._statutory_tax_calculator = statutory_tax_calculator or StatutoryTaxCalculator(
            parameter_service
        )

    async def calculate_batch(self, payroll_run_id: uuid.UUID) -> Sequence[Payslip]:
        """Processes every eligible employee for `payroll_run_id` as one batch.

        "Eligible" means: an active Compensation row effective as of the
        run's `period_end`, in the run's own currency (D8/E7). Transitions
        the run `DRAFT -> PROCESSING` (idempotent if already `PROCESSING`,
        D9) before processing and `PROCESSING -> COMPLETED` after -- raises
        `PayrollRunAlreadyCompletedError` if the run is already
        `COMPLETED`.
        """
        payroll_run = await self._payroll_run_service.get(payroll_run_id)
        if payroll_run is None:
            raise PayrollRunNotFoundError(str(payroll_run_id))
        if payroll_run.status == PayrollRunStatus.COMPLETED:
            raise PayrollRunAlreadyCompletedError(str(payroll_run_id))
        period_start, period_end, currency = self._require_period(payroll_run)

        await self._payroll_run_service.start_processing(payroll_run_id)

        # Rerun support (D9): clear any Payslips already recorded for this
        # run before recomputing -- safe because the run is confirmed not
        # COMPLETED above, and PayslipService.delete_by_payroll_run
        # re-checks that itself (defense in depth).
        await self._payslip_service.delete_by_payroll_run(payroll_run_id)

        eligible = await self._compensation_service.list_active_as_of(period_end)
        eligible_employee_ids = {
            compensation.employee_id
            for compensation in eligible
            if compensation.base_salary_currency == currency
        }

        created: list[Payslip] = []
        for employee_id in eligible_employee_ids:
            try:
                payslip = await self.calculate(payroll_run_id, employee_id)
            except DuplicatePayslipError:
                continue
            created.append(payslip)

        await self._payroll_run_service.complete(payroll_run_id)
        return created

    async def calculate(self, payroll_run_id: uuid.UUID, employee_id: uuid.UUID) -> Payslip:
        payroll_run = await self._payroll_run_service.get(payroll_run_id)
        if payroll_run is None:
            raise PayrollRunNotFoundError(str(payroll_run_id))
        if payroll_run.status == PayrollRunStatus.COMPLETED:
            raise PayrollRunAlreadyCompletedError(str(payroll_run_id))
        period_start, period_end, currency = self._require_period(payroll_run)

        compensation = await self._compensation_service.get_by_employee(
            employee_id, as_of_date=period_end
        )
        if compensation is None:
            raise CompensationNotFoundError(str(employee_id))
        if not compensation.is_active:
            raise CompensationInactiveError(str(employee_id))
        if compensation.base_salary_currency != currency:
            raise CompensationCurrencyMismatchError(
                f"Compensation currency {compensation.base_salary_currency!r} does not "
                f"match PayrollRun currency {currency!r}"
            )

        existing = await self._payslip_service.get_by_employee_and_payroll_run(
            employee_id, payroll_run_id
        )
        if existing is not None:
            raise DuplicatePayslipError(f"{employee_id}:{payroll_run_id}")

        line_items: list[PayslipLineItemCreate] = []

        base_salary = Money(compensation.base_salary_amount, compensation.base_salary_currency)
        line_items.append(
            PayslipLineItemCreate(
                component_type=PayslipLineItemType.BASE_SALARY,
                label="Base Salary",
                line_amount=base_salary.amount,
                line_currency=base_salary.currency,
                source_id=compensation.id,
            )
        )

        for allowance in await self._allowance_service.list_active_for_employee(
            employee_id, period_end
        ):
            amount = Money(allowance.allowance_amount, allowance.allowance_currency)
            line_items.append(
                PayslipLineItemCreate(
                    component_type=PayslipLineItemType.ALLOWANCE,
                    label=f"Allowance ({allowance.allowance_type})",
                    line_amount=amount.amount,
                    line_currency=amount.currency,
                    source_id=allowance.id,
                )
            )

        overtime_item = await self._overtime_calculator.compute(
            employee_id, compensation, period_start, period_end
        )
        if overtime_item is not None:
            line_items.append(overtime_item)

        deduction_item = await self._attendance_leave_deduction_calculator.compute(
            employee_id, compensation, period_start, period_end
        )
        if deduction_item is not None:
            line_items.append(deduction_item)

        for deduction in await self._deduction_service.list_by_employee_and_payroll_run(
            employee_id, payroll_run_id
        ):
            amount = Money(deduction.deduction_amount, deduction.deduction_currency)
            line_items.append(
                PayslipLineItemCreate(
                    component_type=PayslipLineItemType.NON_STATUTORY_DEDUCTION,
                    label="Deduction",
                    line_amount=amount.amount,
                    line_currency=amount.currency,
                    source_id=deduction.id,
                )
            )

        gross = self._sum_earnings(line_items)

        tax_item = await self._statutory_tax_calculator.compute(gross, period_end)
        if tax_item is not None:
            line_items.append(tax_item)

        net_amount = gross.amount - self._sum_deductions(line_items)

        return await self._payslip_service.create(
            PayslipCreate(
                employee_id=employee_id,
                payroll_run_id=payroll_run_id,
                gross_salary_amount=gross.amount,
                gross_salary_currency=gross.currency,
                net_salary_amount=net_amount,
                net_salary_currency=gross.currency,
            ),
            line_items=line_items,
        )

    @staticmethod
    def _require_period(payroll_run: PayrollRun) -> tuple[date, date, str]:
        """Narrows `PayrollRun.period_start`/`period_end`/`currency` from
        their nullable model type (nullable only for Iteration 1-3
        historical-compatibility, `models/payroll_run.py`) to guaranteed
        values, raising `PayrollRunMissingPeriodError` for any run that
        predates Advanced Payroll and genuinely has none configured."""
        period_start = payroll_run.period_start
        period_end = payroll_run.period_end
        currency = payroll_run.currency
        if period_start is None or period_end is None or currency is None:
            raise PayrollRunMissingPeriodError(
                f"PayrollRun {payroll_run.id} has no period/currency configured "
                "and cannot be calculated by Advanced Payroll"
            )
        return period_start, period_end, currency

    @staticmethod
    def _sum_earnings(line_items: Sequence[PayslipLineItemCreate]) -> Money:
        currency = line_items[0].line_currency
        total = sum(
            (
                item.line_amount
                for item in line_items
                if item.component_type in EARNING_LINE_ITEM_TYPES
            ),
            Decimal(0),
        )
        return Money(total, currency)

    @staticmethod
    def _sum_deductions(line_items: Sequence[PayslipLineItemCreate]) -> Decimal:
        return sum(
            (
                item.line_amount
                for item in line_items
                if item.component_type in DEDUCTION_LINE_ITEM_TYPES
            ),
            Decimal(0),
        )
