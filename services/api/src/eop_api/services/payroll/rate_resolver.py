from datetime import date

from eop_api.foundation.monetary.types import Money
from eop_api.models.compensation import Compensation
from eop_api.services.payroll_statutory_parameter import PayrollStatutoryParameterService

STANDARD_WORKING_DAYS_PARAMETER_KEY = "STANDARD_WORKING_DAYS_PER_MONTH"
STANDARD_DAILY_HOURS_PARAMETER_KEY = "STANDARD_DAILY_HOURS"


class PayrollRateResolver:
    """Derives daily/hourly pay rates from Compensation's base salary.

    Implements D3 (`business-decision-package.md`): proration/daily-rate
    calculation belongs to the Payroll Rate / Compensation boundary, never
    Attendance. Lives entirely inside Payroll Calculation's own module --
    `AttendanceEvent`, `LeaveRequest`, `OvertimeRequest`, and `Timesheet`
    are never modified or consulted here.

    Reads `Compensation.base_salary` (already resolved by the caller as of
    the relevant date) and two configurable parameters
    (`STANDARD_WORKING_DAYS_PER_MONTH`, `STANDARD_DAILY_HOURS`) via
    `PayrollStatutoryParameterService` -- never a hard-coded constant, per
    D2/E4. Both parameters must be explicitly configured before any
    proration/overtime calculation can succeed
    (`MissingStatutoryParameterError` otherwise) -- a deliberate fail-loud
    default, not a business rule this class invents.
    """

    def __init__(
        self,
        parameter_service: PayrollStatutoryParameterService | None = None,
    ) -> None:
        self._parameter_service = parameter_service or PayrollStatutoryParameterService()

    async def daily_rate(self, compensation: Compensation, as_of_date: date) -> Money:
        base = Money(compensation.base_salary_amount, compensation.base_salary_currency)
        working_days = await self._parameter_service.get_value(
            STANDARD_WORKING_DAYS_PARAMETER_KEY, as_of_date
        )
        return Money(base.amount / working_days, base.currency)

    async def hourly_rate(self, compensation: Compensation, as_of_date: date) -> Money:
        daily = await self.daily_rate(compensation, as_of_date)
        daily_hours = await self._parameter_service.get_value(
            STANDARD_DAILY_HOURS_PARAMETER_KEY, as_of_date
        )
        return Money(daily.amount / daily_hours, daily.currency)
