import uuid
from datetime import date
from decimal import Decimal

import pytest

from eop_api.models.compensation import Compensation
from eop_api.services.payroll.attendance_leave_deduction_calculator import (
    AttendanceLeaveDeductionCalculator,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _compensation() -> Compensation:
    return Compensation(
        id=uuid.uuid4(),
        employee_id=uuid.uuid4(),
        base_salary_amount=Decimal("4400000.00"),
        base_salary_currency="IDR",
        effective_from=date(2026, 1, 1),
        is_active=True,
    )


async def test_compute_always_returns_none() -> None:
    """No day-of-week/scheduled-work-day concept exists anywhere in this
    repository (Work Schedule remains Blocked, per this class's own
    docstring) -- treating every `ReconciliationService` "absent" day as
    deductible would incorrectly deduct pay for ordinary weekends, so this
    calculator intentionally computes no deduction until that gap is
    resolved. This test locks in that safe default; it must not start
    silently producing deductions without a corresponding, deliberate
    change here."""
    calculator = AttendanceLeaveDeductionCalculator()

    result = await calculator.compute(
        uuid.uuid4(), _compensation(), date(2026, 1, 1), date(2026, 1, 31)
    )

    assert result is None
