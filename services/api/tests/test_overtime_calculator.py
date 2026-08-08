import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import date, datetime, time
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.models.compensation import Compensation
from eop_api.repositories.department import DepartmentRepository
from eop_api.repositories.employment_status import EmploymentStatusRepository
from eop_api.repositories.employment_type import EmploymentTypeRepository
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.job_grade import JobGradeRepository
from eop_api.repositories.location import LocationRepository
from eop_api.repositories.location_type import LocationTypeRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.overtime_request import OvertimeRequestRepository
from eop_api.repositories.position import PositionRepository
from eop_api.repositories.shift import ShiftRepository
from eop_api.repositories.team import TeamRepository
from eop_api.schemas.payroll_statutory_parameter import PayrollStatutoryParameterCreate
from eop_api.services.payroll.overtime_calculator import OvertimeCalculator
from eop_api.services.payroll.rate_resolver import PayrollRateResolver
from eop_api.services.payroll_statutory_parameter import PayrollStatutoryParameterService
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio


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
                    "payroll_statutory_parameters CASCADE"
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
) -> OvertimeCalculator:
    return OvertimeCalculator(
        rate_resolver=PayrollRateResolver(parameter_service),
        parameter_service=parameter_service,
        uow_factory=uow_factory,
    )


@pytest.fixture
async def employee_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
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
        return employee.id


def _compensation(employee_id: uuid.UUID, amount: Decimal = Decimal("4400000.00")) -> Compensation:
    return Compensation(
        id=uuid.uuid4(),
        employee_id=employee_id,
        base_salary_amount=amount,
        base_salary_currency="IDR",
        effective_from=date(2026, 1, 1),
        is_active=True,
    )


async def _seed_rate_parameters(parameter_service: PayrollStatutoryParameterService) -> None:
    await parameter_service.create(
        PayrollStatutoryParameterCreate(
            key="STANDARD_WORKING_DAYS_PER_MONTH",
            value=Decimal("22"),
            effective_from=date(2026, 1, 1),
        )
    )
    await parameter_service.create(
        PayrollStatutoryParameterCreate(
            key="STANDARD_DAILY_HOURS", value=Decimal("8"), effective_from=date(2026, 1, 1)
        )
    )
    await parameter_service.create(
        PayrollStatutoryParameterCreate(
            key="OVERTIME_MULTIPLIER_WEEKDAY",
            value=Decimal("1.5"),
            effective_from=date(2026, 1, 1),
        )
    )


async def test_compute_returns_none_with_no_overtime_requests(
    calculator: OvertimeCalculator, employee_id: uuid.UUID
):
    result = await calculator.compute(
        employee_id, _compensation(employee_id), date(2026, 1, 1), date(2026, 1, 31)
    )

    assert result is None


async def test_compute_converts_approved_overtime_to_pay(
    calculator: OvertimeCalculator,
    parameter_service: PayrollStatutoryParameterService,
    employee_id: uuid.UUID,
    session_factory: Callable[[], AsyncSession],
):
    await _seed_rate_parameters(parameter_service)
    async with session_factory() as session:
        await OvertimeRequestRepository(session).create(
            employee_id=employee_id,
            overtime_date=date(2026, 1, 15),
            start_time=time(18, 0),
            end_time=time(20, 0),
            status="approved",
        )
        await session.commit()

    result = await calculator.compute(
        employee_id, _compensation(employee_id), date(2026, 1, 1), date(2026, 1, 31)
    )

    assert result is not None
    # hourly_rate = 4,400,000 / 22 / 8 = 25,000; 2h * 25,000 * 1.5 = 75,000
    assert result.line_amount == Decimal("75000.00")
    assert result.component_type == "OVERTIME"


async def test_compute_ignores_pending_overtime(
    calculator: OvertimeCalculator,
    employee_id: uuid.UUID,
    session_factory: Callable[[], AsyncSession],
):
    async with session_factory() as session:
        await OvertimeRequestRepository(session).create(
            employee_id=employee_id,
            overtime_date=date(2026, 1, 15),
            start_time=time(18, 0),
            end_time=time(20, 0),
            status="pending",
        )
        await session.commit()

    result = await calculator.compute(
        employee_id, _compensation(employee_id), date(2026, 1, 1), date(2026, 1, 31)
    )

    assert result is None


async def test_compute_sums_multiple_approved_requests(
    calculator: OvertimeCalculator,
    parameter_service: PayrollStatutoryParameterService,
    employee_id: uuid.UUID,
    session_factory: Callable[[], AsyncSession],
):
    await _seed_rate_parameters(parameter_service)
    async with session_factory() as session:
        repo = OvertimeRequestRepository(session)
        await repo.create(
            employee_id=employee_id,
            overtime_date=date(2026, 1, 10),
            start_time=time(18, 0),
            end_time=time(19, 0),
            status="approved",
        )
        await repo.create(
            employee_id=employee_id,
            overtime_date=date(2026, 1, 20),
            start_time=time(18, 0),
            end_time=time(19, 0),
            status="approved",
        )
        await session.commit()

    result = await calculator.compute(
        employee_id, _compensation(employee_id), date(2026, 1, 1), date(2026, 1, 31)
    )

    assert result is not None
    # 2 hours total * 25,000 * 1.5 = 75,000
    assert result.line_amount == Decimal("75000.00")
