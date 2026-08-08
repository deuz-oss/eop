from datetime import date
from decimal import Decimal

from eop_api.core.payroll import PayslipLineItemType
from eop_api.foundation.monetary.types import Money
from eop_api.schemas.payslip_line_item import PayslipLineItemCreate
from eop_api.services.payroll_statutory_parameter import PayrollStatutoryParameterService

STATUTORY_TAX_RATE_PARAMETER_KEY = "STATUTORY_TAX_RATE"


class StatutoryTaxCalculator:
    """Computes statutory tax on gross pay for one payroll period.

    Implements D2/E4 (`business-decision-package.md`): the calculation
    engine is code-based (this class); the rate itself is configurable
    data (`PayrollStatutoryParameter`, read by key via
    `PayrollStatutoryParameterService`) -- never a generic expression/rule
    engine.

    Flat-percentage-of-gross is the narrowest defensible v1 formula shape
    given no specified bracket/formula structure (`implementation-plan.md`
    §7/§10) -- swapping in a real progressive formula later is a code
    change to this one class using the same parameter store, not a schema
    change.

    Unlike overtime/rate parameters, an unconfigured tax rate defaults to
    `0` (`get_value_or_default`) rather than failing loud: Advanced Payroll
    must remain usable with zero configuration, preserving Iteration 1-3's
    existing gross = net behavior until an admin actually configures a
    rate -- failing every calculation until a tax rate exists would
    regress already-shipped behavior, not merely be conservative.
    """

    def __init__(self, parameter_service: PayrollStatutoryParameterService | None = None) -> None:
        self._parameter_service = parameter_service or PayrollStatutoryParameterService()

    async def compute(self, gross: Money, as_of_date: date) -> PayslipLineItemCreate | None:
        rate = await self._parameter_service.get_value_or_default(
            STATUTORY_TAX_RATE_PARAMETER_KEY, as_of_date, Decimal(0)
        )
        if rate == 0:
            return None

        amount = Money(gross.amount * rate, gross.currency)
        return PayslipLineItemCreate(
            component_type=PayslipLineItemType.STATUTORY_DEDUCTION,
            label="Statutory Tax",
            line_amount=amount.amount,
            line_currency=amount.currency,
            source_id=None,
        )
