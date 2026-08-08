import uuid
from datetime import date

from eop_api.models.compensation import Compensation
from eop_api.schemas.payslip_line_item import PayslipLineItemCreate
from eop_api.services.payroll.rate_resolver import PayrollRateResolver
from eop_api.services.reconciliation import ReconciliationService


class AttendanceLeaveDeductionCalculator:
    """Computes one employee's attendance/leave-driven pay deduction for one period.

    Implements D5 (`business-decision-package.md`): Payroll owns the
    financial consequence of attendance/leave facts; Attendance/Leave
    themselves remain pure fact sources -- reads (would read)
    `ReconciliationService.get_range`'s unmodified per-day classification,
    never writing to `AttendanceEvent`/`LeaveRequest`/`LeaveBalance`.

    **Currently always returns `None` (produces no deduction).** Discovered
    during implementation, not assumed in `implementation-plan.md` §7: a
    correct deduction must not treat every `ReconciliationService` "absent"
    day as deductible, because that would systematically deduct pay for
    ordinary weekends -- `ReconciliationService`
    (`ATTENDANCE_RECONCILIATION_DESIGN.md`, v1 scope, unmodified here) has
    no concept of an employee's *scheduled* work days; `Shift` carries only
    a daily time-of-day template (`start_time`/`end_time`), never a weekly
    pattern. Correctly scoping this deduction requires exactly the concept
    the "Work Schedule" capability would provide, and that capability is
    already recorded **Blocked, pending business decisions** elsewhere in
    this repository's governance
    (`docs/architecture/00-governance/ARCHITECTURE_STATUS.md`,
    `capabilities/work-schedule/`). Shipping a formula that ignores this
    gap would not be a conservative default -- it would be wrong for the
    common case.

    This class exists and is wired into `PayrollCalculationService` so D5's
    ownership is honored in shape (Payroll, not Attendance, computes this)
    without shipping incorrect numbers. Once Work Schedule resolves the
    scheduled-work-day gap, `compute` is the one place to implement the
    real per-day computation against `ReconciliationService.get_range` --
    no `PayrollCalculationService` or schema change would be required.
    """

    def __init__(
        self,
        rate_resolver: PayrollRateResolver | None = None,
        reconciliation_service: ReconciliationService | None = None,
    ) -> None:
        self._rate_resolver = rate_resolver or PayrollRateResolver()
        self._reconciliation_service = reconciliation_service or ReconciliationService()

    async def compute(
        self,
        employee_id: uuid.UUID,
        compensation: Compensation,
        period_start: date,
        period_end: date,
    ) -> PayslipLineItemCreate | None:
        return None
