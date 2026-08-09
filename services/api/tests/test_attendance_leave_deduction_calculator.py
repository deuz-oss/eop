import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.attendance import EventSource, EventType
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.models.compensation import Compensation
from eop_api.repositories.attendance_event import AttendanceEventRepository
from eop_api.repositories.department import DepartmentRepository
from eop_api.repositories.employment_status import EmploymentStatusRepository
from eop_api.repositories.employment_type import EmploymentTypeRepository
from eop_api.repositories.holiday import HolidayRepository
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.job_grade import JobGradeRepository
from eop_api.repositories.leave_request import LeaveRequestRepository
from eop_api.repositories.location import LocationRepository
from eop_api.repositories.location_type import LocationTypeRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.position import PositionRepository
from eop_api.repositories.shift import ShiftRepository
from eop_api.repositories.team import TeamRepository
from eop_api.repositories.work_schedule import WorkScheduleRepository
from eop_api.schemas.payroll_statutory_parameter import PayrollStatutoryParameterCreate
from eop_api.services.payroll.attendance_leave_deduction_calculator import (
    AttendanceLeaveDeductionCalculator,
)
from eop_api.services.payroll.rate_resolver import PayrollRateResolver
from eop_api.services.payroll_statutory_parameter import PayrollStatutoryParameterService
from eop_api.services.reconciliation import ReconciliationService
from eop_api.services.work_schedule import WorkScheduleService
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio

# All working-week fixtures use January 2026, where: Jan 5/12/19/26 are
# Mondays, Jan 7 is a Wednesday, Jan 10/17 are Saturdays, Jan 11 is a Sunday.


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session_factory() -> AsyncGenerator[Callable[[], AsyncSession]]:
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory: Callable[[], AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)

    try:
        yield factory
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "TRUNCATE TABLE organizations, locations, location_types, "
                    "job_grades, employment_types, employment_statuses, shifts, "
                    "payroll_statutory_parameters, holidays CASCADE"
                )
            )
        await engine.dispose()


@pytest.fixture
def uow_factory(
    session_factory: Callable[[], AsyncSession],
) -> Callable[[], SQLAlchemyUnitOfWork]:
    return lambda: SQLAlchemyUnitOfWork(session_factory)  # noqa: E731


@pytest.fixture
def parameter_service(
    uow_factory: Callable[[], SQLAlchemyUnitOfWork],
) -> PayrollStatutoryParameterService:
    return PayrollStatutoryParameterService(uow_factory)


@pytest.fixture
def calculator(
    uow_factory: Callable[[], SQLAlchemyUnitOfWork],
    parameter_service: PayrollStatutoryParameterService,
) -> AttendanceLeaveDeductionCalculator:
    return AttendanceLeaveDeductionCalculator(
        rate_resolver=PayrollRateResolver(parameter_service),
        reconciliation_service=ReconciliationService(uow_factory),
        work_schedule_service=WorkScheduleService(uow_factory),
    )


@pytest.fixture
async def employee_and_shift(
    session_factory: Callable[[], AsyncSession],
) -> tuple[uuid.UUID, uuid.UUID]:
    async with session_factory() as session:
        organization = await OrganizationRepository(session).create(name="Acme Corp")
        department = await DepartmentRepository(session).create(
            organization_id=organization.id, code="ENG", name="Engineering"
        )
        position = await PositionRepository(session).create(
            organization_id=organization.id,
            department_id=department.id,
            code="ENG-1",
            name="Engineer",
        )
        team = await TeamRepository(session).create(
            organization_id=organization.id,
            department_id=department.id,
            code="BACKEND",
            name="Backend",
        )
        location_type = await LocationTypeRepository(session).create(code="OFFICE", name="Office")
        location = await LocationRepository(session).create(
            code="HQ", name="HQ", location_type_id=location_type.id
        )
        job_grade = await JobGradeRepository(session).create(code="L1", name="Junior", level=1)
        employment_type = await EmploymentTypeRepository(session).create(
            code="FT", name="Full-Time"
        )
        employment_status = await EmploymentStatusRepository(session).create(
            code="ACTIVE", name="Active"
        )
        shift = await ShiftRepository(session).create(
            code="DAY",
            name="Day Shift",
            start_time=datetime(2024, 1, 1, 9, 0).time(),
            end_time=datetime(2024, 1, 1, 17, 0).time(),
        )
        employee = await HrEmployeeRepository(session).create(
            employee_number="EMP-1",
            first_name="Ada",
            last_name="Lovelace",
            full_name="Ada Lovelace",
            email="ada@example.com",
            organization_id=organization.id,
            department_id=department.id,
            position_id=position.id,
            team_id=team.id,
            location_id=location.id,
            job_grade_id=job_grade.id,
            employment_type_id=employment_type.id,
            employment_status_id=employment_status.id,
            shift_id=shift.id,
            hire_date=date(2024, 1, 15),
            employment_status="active",
        )
        await session.commit()
        return employee.id, shift.id


@pytest.fixture
async def employee_id(employee_and_shift: tuple[uuid.UUID, uuid.UUID]) -> uuid.UUID:
    return employee_and_shift[0]


def _compensation(employee_id: uuid.UUID, amount: Decimal = Decimal("4400000.00")) -> Compensation:
    return Compensation(
        id=uuid.uuid4(),
        employee_id=employee_id,
        base_salary_amount=amount,
        base_salary_currency="IDR",
        effective_from=date(2026, 1, 1),
        is_active=True,
    )


async def _seed_working_days_parameter(parameter_service: PayrollStatutoryParameterService) -> None:
    await parameter_service.create(
        PayrollStatutoryParameterCreate(
            key="STANDARD_WORKING_DAYS_PER_MONTH",
            value=Decimal("22"),
            effective_from=date(2026, 1, 1),
        )
    )


async def _create_work_schedule(
    session_factory: Callable[[], AsyncSession],
    employee_id: uuid.UUID,
    shift_id: uuid.UUID,
    *,
    effective_from: date = date(2026, 1, 1),
    effective_to: date | None = None,
    works_monday: bool = True,
    works_tuesday: bool = True,
    works_wednesday: bool = True,
    works_thursday: bool = True,
    works_friday: bool = True,
    works_saturday: bool = False,
    works_sunday: bool = False,
    corrects_id: uuid.UUID | None = None,
) -> uuid.UUID:
    async with session_factory() as session:
        work_schedule = await WorkScheduleRepository(session).create(
            employee_id=employee_id,
            shift_id=shift_id,
            effective_from=effective_from,
            effective_to=effective_to,
            works_monday=works_monday,
            works_tuesday=works_tuesday,
            works_wednesday=works_wednesday,
            works_thursday=works_thursday,
            works_friday=works_friday,
            works_saturday=works_saturday,
            works_sunday=works_sunday,
            corrects_id=corrects_id,
        )
        await session.commit()
        return work_schedule.id


async def _mark_present(
    session_factory: Callable[[], AsyncSession],
    employee_id: uuid.UUID,
    shift_id: uuid.UUID,
    event_date: date,
) -> None:
    async with session_factory() as session:
        await AttendanceEventRepository(session).create(
            employee_id=employee_id,
            shift_id=shift_id,
            event_type=EventType.CLOCK_IN,
            event_time=datetime.combine(event_date, datetime.min.time(), tzinfo=UTC),
            source=EventSource.SYSTEM,
        )
        await session.commit()


async def _mark_holiday(session_factory: Callable[[], AsyncSession], holiday_date: date) -> None:
    async with session_factory() as session:
        await HolidayRepository(session).create(
            code=f"H-{holiday_date.isoformat()}", name="Holiday", holiday_date=holiday_date
        )
        await session.commit()


async def _mark_approved_leave(
    session_factory: Callable[[], AsyncSession],
    employee_id: uuid.UUID,
    leave_date: date,
) -> None:
    async with session_factory() as session:
        await LeaveRequestRepository(session).create(
            employee_id=employee_id,
            start_date=leave_date,
            end_date=leave_date,
            status="approved",
        )
        await session.commit()


async def test_absent_and_scheduled_day_is_deducted(
    calculator: AttendanceLeaveDeductionCalculator,
    parameter_service: PayrollStatutoryParameterService,
    employee_and_shift: tuple[uuid.UUID, uuid.UUID],
    session_factory: Callable[[], AsyncSession],
):
    employee_id, shift_id = employee_and_shift
    await _seed_working_days_parameter(parameter_service)
    await _create_work_schedule(session_factory, employee_id, shift_id)

    result = await calculator.compute(
        employee_id, _compensation(employee_id), date(2026, 1, 5), date(2026, 1, 5)
    )

    assert result is not None
    # daily_rate = 4,400,000 / 22 = 200,000
    assert result.line_amount == Decimal("200000.00")
    assert result.component_type == "ATTENDANCE_DEDUCTION"


async def test_absent_and_non_working_weekday_is_not_deducted(
    calculator: AttendanceLeaveDeductionCalculator,
    parameter_service: PayrollStatutoryParameterService,
    employee_and_shift: tuple[uuid.UUID, uuid.UUID],
    session_factory: Callable[[], AsyncSession],
):
    employee_id, shift_id = employee_and_shift
    await _seed_working_days_parameter(parameter_service)
    # Wednesday is explicitly not worked, distinct from the weekend.
    await _create_work_schedule(session_factory, employee_id, shift_id, works_wednesday=False)

    result = await calculator.compute(
        employee_id, _compensation(employee_id), date(2026, 1, 7), date(2026, 1, 7)
    )

    assert result is None


async def test_weekend_absence_not_deducted_when_schedule_marks_it_non_working(
    calculator: AttendanceLeaveDeductionCalculator,
    parameter_service: PayrollStatutoryParameterService,
    employee_and_shift: tuple[uuid.UUID, uuid.UUID],
    session_factory: Callable[[], AsyncSession],
):
    employee_id, shift_id = employee_and_shift
    await _seed_working_days_parameter(parameter_service)
    await _create_work_schedule(session_factory, employee_id, shift_id)  # Sat/Sun default False

    result = await calculator.compute(
        employee_id, _compensation(employee_id), date(2026, 1, 10), date(2026, 1, 10)
    )

    assert result is None


async def test_multiple_deductible_days_produce_one_aggregated_line(
    calculator: AttendanceLeaveDeductionCalculator,
    parameter_service: PayrollStatutoryParameterService,
    employee_and_shift: tuple[uuid.UUID, uuid.UUID],
    session_factory: Callable[[], AsyncSession],
):
    employee_id, shift_id = employee_and_shift
    await _seed_working_days_parameter(parameter_service)
    await _create_work_schedule(session_factory, employee_id, shift_id)
    # Mark every day between the two target Mondays present, so only Jan 5
    # and Jan 12 remain classified `absent`.
    for day in range(6, 12):
        await _mark_present(session_factory, employee_id, shift_id, date(2026, 1, day))

    result = await calculator.compute(
        employee_id, _compensation(employee_id), date(2026, 1, 5), date(2026, 1, 12)
    )

    assert result is not None
    # Jan 5 and Jan 12 are both absent, scheduled Mondays -> 2 * 200,000
    assert result.line_amount == Decimal("400000.00")
    assert result.label == "Attendance Deduction (2 days)"


async def test_absent_day_with_no_work_schedule_is_not_deducted(
    calculator: AttendanceLeaveDeductionCalculator,
    parameter_service: PayrollStatutoryParameterService,
    employee_id: uuid.UUID,
):
    await _seed_working_days_parameter(parameter_service)
    # No WorkSchedule row created for this employee at all.

    result = await calculator.compute(
        employee_id, _compensation(employee_id), date(2026, 1, 5), date(2026, 1, 5)
    )

    assert result is None


async def test_present_day_is_not_deducted(
    calculator: AttendanceLeaveDeductionCalculator,
    parameter_service: PayrollStatutoryParameterService,
    employee_and_shift: tuple[uuid.UUID, uuid.UUID],
    session_factory: Callable[[], AsyncSession],
):
    employee_id, shift_id = employee_and_shift
    await _seed_working_days_parameter(parameter_service)
    await _create_work_schedule(session_factory, employee_id, shift_id)
    await _mark_present(session_factory, employee_id, shift_id, date(2026, 1, 5))

    result = await calculator.compute(
        employee_id, _compensation(employee_id), date(2026, 1, 5), date(2026, 1, 5)
    )

    assert result is None


async def test_holiday_and_leave_are_never_converted_to_deductions(
    calculator: AttendanceLeaveDeductionCalculator,
    parameter_service: PayrollStatutoryParameterService,
    employee_and_shift: tuple[uuid.UUID, uuid.UUID],
    session_factory: Callable[[], AsyncSession],
):
    employee_id, shift_id = employee_and_shift
    await _seed_working_days_parameter(parameter_service)
    # Every day of the week is "worked" so weekday filtering cannot be the
    # reason these are excluded -- only the holiday/leave classification is.
    await _create_work_schedule(
        session_factory,
        employee_id,
        shift_id,
        works_saturday=True,
        works_sunday=True,
    )
    await _mark_holiday(session_factory, date(2026, 1, 5))
    await _mark_approved_leave(session_factory, employee_id, date(2026, 1, 6))

    result = await calculator.compute(
        employee_id, _compensation(employee_id), date(2026, 1, 5), date(2026, 1, 6)
    )

    assert result is None


async def test_historical_work_schedule_resolved_per_individual_date(
    calculator: AttendanceLeaveDeductionCalculator,
    parameter_service: PayrollStatutoryParameterService,
    employee_and_shift: tuple[uuid.UUID, uuid.UUID],
    session_factory: Callable[[], AsyncSession],
):
    employee_id, shift_id = employee_and_shift
    await _seed_working_days_parameter(parameter_service)
    # First half of January: Mondays not worked.
    await _create_work_schedule(
        session_factory,
        employee_id,
        shift_id,
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 1, 15),
        works_monday=False,
    )
    # From Jan 16 onward: Mondays worked.
    await _create_work_schedule(
        session_factory,
        employee_id,
        shift_id,
        effective_from=date(2026, 1, 16),
        effective_to=None,
        works_monday=True,
    )
    # Mark every other day present, isolating Jan 5 and Jan 19 as the only
    # days classified `absent`.
    for day in range(1, 32):
        if day not in (5, 19):
            await _mark_present(session_factory, employee_id, shift_id, date(2026, 1, day))

    result = await calculator.compute(
        employee_id, _compensation(employee_id), date(2026, 1, 1), date(2026, 1, 31)
    )

    assert result is not None
    # Jan 5 (first schedule, Monday not worked) is skipped; Jan 19
    # (second schedule, Monday worked) is deductible -> 1 * 200,000.
    assert result.line_amount == Decimal("200000.00")


async def test_work_schedule_correction_precedence_is_respected(
    calculator: AttendanceLeaveDeductionCalculator,
    parameter_service: PayrollStatutoryParameterService,
    employee_and_shift: tuple[uuid.UUID, uuid.UUID],
    session_factory: Callable[[], AsyncSession],
):
    employee_id, shift_id = employee_and_shift
    await _seed_working_days_parameter(parameter_service)
    original_id = await _create_work_schedule(
        session_factory, employee_id, shift_id, works_monday=False
    )
    # The correction supersedes the original for the same effective window --
    # resolved entirely by `WorkScheduleService.get_by_employee`, not
    # reimplemented by the calculator.
    await _create_work_schedule(
        session_factory, employee_id, shift_id, works_monday=True, corrects_id=original_id
    )

    result = await calculator.compute(
        employee_id, _compensation(employee_id), date(2026, 1, 5), date(2026, 1, 5)
    )

    assert result is not None
    assert result.line_amount == Decimal("200000.00")


async def test_no_deductible_days_returns_none(
    calculator: AttendanceLeaveDeductionCalculator,
    parameter_service: PayrollStatutoryParameterService,
    employee_and_shift: tuple[uuid.UUID, uuid.UUID],
    session_factory: Callable[[], AsyncSession],
):
    employee_id, shift_id = employee_and_shift
    await _seed_working_days_parameter(parameter_service)
    await _create_work_schedule(session_factory, employee_id, shift_id)
    for day in range(1, 32):
        await _mark_present(session_factory, employee_id, shift_id, date(2026, 1, day))

    result = await calculator.compute(
        employee_id, _compensation(employee_id), date(2026, 1, 1), date(2026, 1, 31)
    )

    assert result is None
