import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.repositories.department import DepartmentRepository
from eop_api.repositories.employment_status import EmploymentStatusRepository
from eop_api.repositories.employment_type import EmploymentTypeRepository
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.job_grade import JobGradeRepository
from eop_api.repositories.location import LocationRepository
from eop_api.repositories.location_type import LocationTypeRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.payroll_run import PayrollRunRepository
from eop_api.repositories.position import PositionRepository
from eop_api.repositories.shift import ShiftRepository
from eop_api.repositories.team import TeamRepository
from eop_api.schemas.compensation import CompensationCreate, CompensationUpdate
from eop_api.services.compensation import CompensationService
from eop_api.services.payroll_calculation import (
    CompensationInactiveError,
    CompensationNotFoundError,
    DuplicatePayslipError,
    PayrollCalculationService,
)
from eop_api.services.payslip import PayslipService
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
                    "payroll_runs CASCADE"
                )
            )
        await engine.dispose()


@pytest.fixture
def uow_factory(
    session_factory: Callable[[], AsyncSession],
) -> Callable[[], SQLAlchemyUnitOfWork]:
    return lambda: SQLAlchemyUnitOfWork(session_factory)  # noqa: E731


@pytest.fixture
def service(uow_factory: Callable[[], SQLAlchemyUnitOfWork]) -> PayrollCalculationService:
    return PayrollCalculationService(uow_factory=uow_factory)


@pytest.fixture
def compensation_service(
    uow_factory: Callable[[], SQLAlchemyUnitOfWork],
) -> CompensationService:
    return CompensationService(uow_factory)


@pytest.fixture
def payslip_service(uow_factory: Callable[[], SQLAlchemyUnitOfWork]) -> PayslipService:
    return PayslipService(uow_factory)


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
            name="Backend Team",
        )
        location_type = await LocationTypeRepository(session).create(
            code="OFFICE", name="Office"
        )
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
            hire_date=datetime(2024, 1, 15).date(),
            employment_status="active",
        )
        await session.commit()
        return employee.id


@pytest.fixture
async def payroll_run_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
    async with session_factory() as session:
        payroll_run = await PayrollRunRepository(session).create(code="RUN-001", name="First Run")
        await session.commit()
        return payroll_run.id


async def test_calculate_sets_net_equal_to_gross(
    service: PayrollCalculationService,
    compensation_service: CompensationService,
    employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    await compensation_service.create(
        CompensationCreate(
            employee_id=employee_id,
            base_salary_amount=Decimal("5000000.00"),
            base_salary_currency="IDR",
            effective_from=date(2026, 1, 1),
        )
    )

    payslip = await service.calculate(payroll_run_id, employee_id)

    assert payslip.gross_salary_amount == Decimal("5000000.00")
    assert payslip.net_salary_amount == Decimal("5000000.00")
    assert payslip.gross_salary_currency == "IDR"
    assert payslip.net_salary_currency == "IDR"
    assert payslip.employee_id == employee_id
    assert payslip.payroll_run_id == payroll_run_id


async def test_calculate_rejects_missing_compensation(
    service: PayrollCalculationService, employee_id: uuid.UUID, payroll_run_id: uuid.UUID
):
    with pytest.raises(CompensationNotFoundError):
        await service.calculate(payroll_run_id, employee_id)


async def test_calculate_rejects_inactive_compensation(
    service: PayrollCalculationService,
    compensation_service: CompensationService,
    employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    compensation = await compensation_service.create(
        CompensationCreate(
            employee_id=employee_id,
            base_salary_amount=Decimal("5000000.00"),
            base_salary_currency="IDR",
            effective_from=date(2026, 1, 1),
        )
    )
    await compensation_service.update(compensation.id, CompensationUpdate(is_active=False))

    with pytest.raises(CompensationInactiveError):
        await service.calculate(payroll_run_id, employee_id)


async def test_calculate_rejects_duplicate_payslip(
    service: PayrollCalculationService,
    compensation_service: CompensationService,
    employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    await compensation_service.create(
        CompensationCreate(
            employee_id=employee_id,
            base_salary_amount=Decimal("5000000.00"),
            base_salary_currency="IDR",
            effective_from=date(2026, 1, 1),
        )
    )
    await service.calculate(payroll_run_id, employee_id)

    with pytest.raises(DuplicatePayslipError):
        await service.calculate(payroll_run_id, employee_id)
