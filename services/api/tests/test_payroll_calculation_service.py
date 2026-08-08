import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.core.payroll import PayrollRunStatus
from eop_api.db.base import Base
from eop_api.models.hr_employee import HrEmployee
from eop_api.models.user import User
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
from eop_api.services.employee_context import EmployeeContext, RequestContext
from eop_api.services.payroll_calculation import (
    CompensationInactiveError,
    CompensationNotFoundError,
    DuplicatePayslipError,
    PayrollCalculationService,
)
from eop_api.services.payroll_run import InvalidPayrollRunTransitionError, PayrollRunService
from eop_api.services.payslip import PayrollRunNotFoundError, PayslipService
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
def payroll_run_service(
    uow_factory: Callable[[], SQLAlchemyUnitOfWork],
) -> PayrollRunService:
    return PayrollRunService(uow_factory)


async def _create_hr_employee(
    session_factory: Callable[[], AsyncSession], *, suffix: str
) -> uuid.UUID:
    async with session_factory() as session:
        organization = await OrganizationRepository(session).create(name=f"Acme Corp {suffix}")
        department = await DepartmentRepository(session).create(
            organization_id=organization.id, code=f"ENG-{suffix}", name="Engineering"
        )
        position = await PositionRepository(session).create(
            organization_id=organization.id,
            department_id=department.id,
            code=f"ENG-1-{suffix}",
            name="Engineer",
        )
        team = await TeamRepository(session).create(
            organization_id=organization.id,
            department_id=department.id,
            code=f"BACKEND-{suffix}",
            name="Backend Team",
        )
        location_type = await LocationTypeRepository(session).create(
            code=f"OFFICE-{suffix}", name="Office"
        )
        location = await LocationRepository(session).create(
            code=f"HQ-{suffix}", name="HQ", location_type_id=location_type.id
        )
        job_grade = await JobGradeRepository(session).create(
            code=f"L1-{suffix}", name="Junior", level=ord(suffix[0]) - ord("a") + 1
        )
        employment_type = await EmploymentTypeRepository(session).create(
            code=f"FT-{suffix}", name="Full-Time"
        )
        employment_status = await EmploymentStatusRepository(session).create(
            code=f"ACTIVE-{suffix}", name="Active"
        )
        shift = await ShiftRepository(session).create(
            code=f"DAY-{suffix}",
            name="Day Shift",
            start_time=datetime(2024, 1, 1, 9, 0).time(),
            end_time=datetime(2024, 1, 1, 17, 0).time(),
        )
        employee = await HrEmployeeRepository(session).create(
            employee_number=f"EMP-{suffix}",
            first_name="Ada",
            last_name="Lovelace",
            full_name="Ada Lovelace",
            email=f"ada-{suffix}@example.com",
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
async def employee_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
    return await _create_hr_employee(session_factory, suffix="a")


@pytest.fixture
async def other_employee_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
    return await _create_hr_employee(session_factory, suffix="b")


@pytest.fixture
async def payroll_run_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
    async with session_factory() as session:
        payroll_run = await PayrollRunRepository(session).create(code="RUN-001", name="First Run")
        await session.commit()
        return payroll_run.id


def _request_context(employee_id: uuid.UUID) -> RequestContext:
    """A `RequestContext` built entirely in memory, scoped to `employee_id`.

    Mirrors `test_compensation_service.py`'s `_request_context` helper --
    used here only so this file's own direct `compensation_service.create`/
    `.update` fixture calls (setup for `PayrollCalculationService`, not
    `PayrollCalculationService` itself, which always calls with
    `request_context=None`, per `services/payroll_calculation.py`) satisfy
    `CompensationService`'s now-required `request_context` parameter as the
    resource's owner.
    """
    user = User(
        id=uuid.uuid4(),
        email="actor@example.com",
        password_hash="hash",
        full_name="Actor",
        is_active=True,
    )
    employee = HrEmployee(
        id=employee_id,
        employee_number="ACT-1",
        first_name="Actor",
        last_name="One",
        full_name="Actor One",
        email="actor@example.com",
        organization_id=uuid.uuid4(),
        department_id=uuid.uuid4(),
        position_id=uuid.uuid4(),
        team_id=uuid.uuid4(),
        location_id=uuid.uuid4(),
        job_grade_id=uuid.uuid4(),
        employment_type_id=uuid.uuid4(),
        employment_status_id=uuid.uuid4(),
        shift_id=uuid.uuid4(),
        hire_date=date(2020, 1, 1),
        employment_status="active",
        user_id=user.id,
    )
    return RequestContext(user=user, employee_context=EmployeeContext(user=user, employee=employee))


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
        ),
        _request_context(employee_id),
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
        ),
        _request_context(employee_id),
    )
    await compensation_service.update(
        compensation.id, CompensationUpdate(is_active=False), _request_context(employee_id)
    )

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
        ),
        _request_context(employee_id),
    )
    await service.calculate(payroll_run_id, employee_id)

    with pytest.raises(DuplicatePayslipError):
        await service.calculate(payroll_run_id, employee_id)


async def _add_active_compensation(
    compensation_service: CompensationService, employee_id: uuid.UUID
) -> None:
    await compensation_service.create(
        CompensationCreate(
            employee_id=employee_id,
            base_salary_amount=Decimal("5000000.00"),
            base_salary_currency="IDR",
            effective_from=date(2026, 1, 1),
        ),
        _request_context(employee_id),
    )


async def test_calculate_batch_processes_eligible_employees(
    service: PayrollCalculationService,
    compensation_service: CompensationService,
    payroll_run_service: PayrollRunService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    await _add_active_compensation(compensation_service, employee_id)
    await _add_active_compensation(compensation_service, other_employee_id)

    payslips = await service.calculate_batch(payroll_run_id)

    assert {p.employee_id for p in payslips} == {employee_id, other_employee_id}
    for payslip in payslips:
        assert payslip.gross_salary_amount == Decimal("5000000.00")
        assert payslip.net_salary_amount == Decimal("5000000.00")

    payroll_run = await payroll_run_service.get(payroll_run_id)
    assert payroll_run is not None
    assert payroll_run.status == PayrollRunStatus.COMPLETED


async def test_calculate_batch_excludes_inactive_compensation(
    service: PayrollCalculationService,
    compensation_service: CompensationService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    await _add_active_compensation(compensation_service, employee_id)
    inactive = await compensation_service.create(
        CompensationCreate(
            employee_id=other_employee_id,
            base_salary_amount=Decimal("3000000.00"),
            base_salary_currency="IDR",
            effective_from=date(2026, 1, 1),
        ),
        _request_context(other_employee_id),
    )
    await compensation_service.update(
        inactive.id, CompensationUpdate(is_active=False), _request_context(other_employee_id)
    )

    payslips = await service.calculate_batch(payroll_run_id)

    assert {p.employee_id for p in payslips} == {employee_id}


async def test_calculate_batch_skips_already_calculated_employee(
    service: PayrollCalculationService,
    compensation_service: CompensationService,
    payslip_service: PayslipService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    """An employee already calculated (outside the batch call) is skipped, not an error."""
    await _add_active_compensation(compensation_service, employee_id)
    await _add_active_compensation(compensation_service, other_employee_id)
    await service.calculate(payroll_run_id, employee_id)

    payslips = await service.calculate_batch(payroll_run_id)

    assert {p.employee_id for p in payslips} == {other_employee_id}
    all_payslips = await payslip_service.list(_request_context(employee_id))
    assert any(p.employee_id == employee_id for p in all_payslips)


async def test_calculate_batch_rejects_missing_payroll_run(
    service: PayrollCalculationService, employee_id: uuid.UUID
):
    with pytest.raises(PayrollRunNotFoundError):
        await service.calculate_batch(uuid.uuid4())


async def test_calculate_batch_rejects_already_completed_run(
    service: PayrollCalculationService,
    compensation_service: CompensationService,
    employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    await _add_active_compensation(compensation_service, employee_id)
    await service.calculate_batch(payroll_run_id)

    with pytest.raises(InvalidPayrollRunTransitionError):
        await service.calculate_batch(payroll_run_id)
