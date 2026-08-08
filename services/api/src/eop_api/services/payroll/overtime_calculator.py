import uuid
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal

from eop_api.core.payroll import PayslipLineItemType
from eop_api.foundation.monetary.types import Money
from eop_api.models.compensation import Compensation
from eop_api.repositories.overtime_request import OvertimeRequestRepository
from eop_api.schemas.payslip_line_item import PayslipLineItemCreate
from eop_api.services.payroll.rate_resolver import PayrollRateResolver
from eop_api.services.payroll_statutory_parameter import PayrollStatutoryParameterService
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

OVERTIME_MULTIPLIER_PARAMETER_KEY = "OVERTIME_MULTIPLIER_WEEKDAY"


class OvertimeCalculator:
    """Computes one employee's overtime pay for one payroll period.

    Implements D4 (`business-decision-package.md`): Payroll owns overtime
    monetary conversion. Reads `OvertimeRequest` (Overtime's own,
    unmodified, approved records) read-only via
    `OvertimeRequestRepository.list_approved_in_range` -- duration
    aggregation and rate conversion both happen here, never inside
    `OvertimeRequestService`/`OvertimeRequest` itself (E3: aggregation
    ownership lives in Payroll, not upstream, per
    `implementation-plan.md` §5/§7).
    """

    def __init__(
        self,
        rate_resolver: PayrollRateResolver | None = None,
        parameter_service: PayrollStatutoryParameterService | None = None,
        uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork,
    ) -> None:
        self._rate_resolver = rate_resolver or PayrollRateResolver()
        self._parameter_service = parameter_service or PayrollStatutoryParameterService()
        self._uow_factory = uow_factory

    async def compute(
        self,
        employee_id: uuid.UUID,
        compensation: Compensation,
        period_start: date,
        period_end: date,
    ) -> PayslipLineItemCreate | None:
        total_hours = Decimal(0)
        async with self._uow_factory() as uow:
            requests = await OvertimeRequestRepository(uow.session).list_approved_in_range(
                employee_id, period_start, period_end
            )
            # Summed inside the UoW's `async with` block, not after: the rows
            # detach once the session closes on exit, and their columns
            # (`overtime_date`/`start_time`/`end_time`) are not expunged/
            # pre-loaded, so accessing them afterward raises
            # `DetachedInstanceError`.
            for request in requests:
                start = datetime.combine(request.overtime_date, request.start_time)
                end = datetime.combine(request.overtime_date, request.end_time)
                total_hours += Decimal((end - start).total_seconds()) / Decimal(3600)

        if total_hours == 0:
            return None

        hourly = await self._rate_resolver.hourly_rate(compensation, period_end)
        multiplier = await self._parameter_service.get_value(
            OVERTIME_MULTIPLIER_PARAMETER_KEY, period_end
        )
        amount = Money(hourly.amount * total_hours * multiplier, hourly.currency)

        return PayslipLineItemCreate(
            component_type=PayslipLineItemType.OVERTIME,
            label=f"Overtime ({total_hours} hours)",
            line_amount=amount.amount,
            line_currency=amount.currency,
            source_id=None,
        )
