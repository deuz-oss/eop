import uuid
from datetime import date
from decimal import Decimal

from eop_api.core.payroll import PayslipLineItemType
from eop_api.foundation.monetary.types import Money
from eop_api.models.compensation import Compensation
from eop_api.schemas.payslip_line_item import PayslipLineItemCreate
from eop_api.services.payroll.rate_resolver import PayrollRateResolver
from eop_api.services.reconciliation import ReconciliationService
from eop_api.services.work_schedule import WorkScheduleService

_ABSENT_STATUS = "absent"


class AttendanceLeaveDeductionCalculator:
    """Computes one employee's attendance/leave-driven pay deduction for one period.

    Implements D5 (`business-decision-package.md`): Payroll owns the
    financial consequence of attendance/leave facts; Attendance/Leave and
    Work Schedule themselves remain pure fact sources -- reads
    `ReconciliationService.get_range`'s unmodified per-day classification
    and `WorkScheduleService.get_by_employee`'s unmodified effective-dated
    resolution, never writing to `AttendanceEvent`/`LeaveRequest`/
    `LeaveBalance`/`WorkSchedule`.

    A day is deductible only when both hold: `ReconciliationService`
    classifies it `absent`, and the employee's `WorkSchedule` effective on
    that date marks the corresponding weekday as worked -- resolving the
    gap this class's own docstring previously named (treating every
    `absent` day as deductible would incorrectly deduct pay for ordinary
    non-working days). `holiday`/`leave` days are never deductible,
    regardless of schedule (D5, unchanged). An employee with no `WorkSchedule`
    row effective on a given date is simply not deductible for that date --
    mirrors `OvertimeCalculator`/`StatutoryTaxCalculator`'s own "no
    applicable data -> no line item" convention, not a fail-loud error.

    `WorkScheduleService.get_by_employee` is called with `request_context=
    None`, exactly like this calculator's own `ReconciliationService` reads
    and `PayrollCalculationService`'s existing `CompensationService`/
    `AllowanceService` reads: a system/batch read, bypassing Work
    Schedule's Owner Only authorization (`get_by_employee` already skips
    authorization whenever `request_context` is `None`), not a new
    authorization mechanism.
    """

    def __init__(
        self,
        rate_resolver: PayrollRateResolver | None = None,
        reconciliation_service: ReconciliationService | None = None,
        work_schedule_service: WorkScheduleService | None = None,
    ) -> None:
        self._rate_resolver = rate_resolver or PayrollRateResolver()
        self._reconciliation_service = reconciliation_service or ReconciliationService()
        self._work_schedule_service = work_schedule_service or WorkScheduleService()

    async def compute(
        self,
        employee_id: uuid.UUID,
        compensation: Compensation,
        period_start: date,
        period_end: date,
    ) -> PayslipLineItemCreate | None:
        results = await self._reconciliation_service.get_range(
            employee_id, period_start, period_end
        )

        total = Decimal(0)
        deductible_days = 0
        for result in results:
            if result.status != _ABSENT_STATUS:
                continue

            work_schedule = await self._work_schedule_service.get_by_employee(
                employee_id, request_context=None, as_of_date=result.date
            )
            if work_schedule is None:
                continue

            works_that_weekday = (
                work_schedule.works_monday,
                work_schedule.works_tuesday,
                work_schedule.works_wednesday,
                work_schedule.works_thursday,
                work_schedule.works_friday,
                work_schedule.works_saturday,
                work_schedule.works_sunday,
            )[result.date.weekday()]
            if not works_that_weekday:
                continue

            daily = await self._rate_resolver.daily_rate(compensation, result.date)
            total += daily.amount
            deductible_days += 1

        if deductible_days == 0:
            return None

        amount = Money(total, compensation.base_salary_currency)
        day_word = "day" if deductible_days == 1 else "days"
        return PayslipLineItemCreate(
            component_type=PayslipLineItemType.ATTENDANCE_DEDUCTION,
            label=f"Attendance Deduction ({deductible_days} {day_word})",
            line_amount=amount.amount,
            line_currency=amount.currency,
            source_id=None,
        )
