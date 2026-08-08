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
from eop_api.schemas.payslip import PayslipCreate
from eop_api.services.employee_context import EmployeeContext, RequestContext
from eop_api.services.payslip import (
    EmployeeNotFoundError,
    PayrollRunNotFoundError,
    PayslipAuthorizationDeniedError,
    PayslipService,
)
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session_factory() -> AsyncGenerator[Callable[[], AsyncSession]]:
    """A session factory backed by the real (migration-managed) tables.

    Unlike the repository tests, the service commits internally (it owns the
    transaction boundary), so rows are truncated after each test instead of
    relying on a rolled-back transaction.
    """
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
def service(session_factory: Callable[[], AsyncSession]) -> PayslipService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return PayslipService(uow_factory)


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
        payroll_run = await PayrollRunRepository(session).create(
            code="RUN-001", name="First Run"
        )
        await session.commit()
        return payroll_run.id


def _request_context(employee_id: uuid.UUID) -> RequestContext:
    """A `RequestContext` built entirely in memory, scoped to `employee_id`.

    Mirrors `test_attendance_event_service.py`'s `_request_context` helper --
    only `employee_context.employee.id` is read by
    `PayslipAuthorizationEvaluator`/`PayslipService`, so the `User`/`HrEmployee`
    here need not be persisted.
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


def _create(employee_id: uuid.UUID, payroll_run_id: uuid.UUID, **overrides) -> PayslipCreate:
    values = {
        "employee_id": employee_id,
        "payroll_run_id": payroll_run_id,
        "gross_salary_amount": Decimal("1000.00"),
        "gross_salary_currency": "IDR",
        "net_salary_amount": Decimal("1000.00"),
        "net_salary_currency": "IDR",
    }
    values.update(overrides)
    return PayslipCreate(**values)


async def test_create_and_get(
    service: PayslipService, employee_id: uuid.UUID, payroll_run_id: uuid.UUID
):
    context = _request_context(employee_id)
    payslip = await service.create(_create(employee_id, payroll_run_id), context)

    fetched = await service.get(payslip.id, context)

    assert fetched is not None
    assert fetched.employee_id == employee_id
    assert fetched.payroll_run_id == payroll_run_id
    assert fetched.gross_salary_amount == Decimal("1000.00")
    assert fetched.net_salary_amount == Decimal("1000.00")


async def test_create_without_context_skips_authorization(
    service: PayslipService, employee_id: uuid.UUID, payroll_run_id: uuid.UUID
):
    """Mirrors `PayrollCalculationService`'s internal, context-free call."""
    payslip = await service.create(_create(employee_id, payroll_run_id))

    assert payslip.employee_id == employee_id


async def test_create_rejects_missing_employee(
    service: PayslipService, payroll_run_id: uuid.UUID
):
    with pytest.raises(EmployeeNotFoundError):
        await service.create(_create(uuid.uuid4(), payroll_run_id))


async def test_create_rejects_missing_payroll_run(
    service: PayslipService, employee_id: uuid.UUID
):
    with pytest.raises(PayrollRunNotFoundError):
        await service.create(_create(employee_id, uuid.uuid4()))


async def test_create_denied_for_non_owner(
    service: PayslipService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    """`employee_id` on the payload does not belong to the calling employee."""
    with pytest.raises(PayslipAuthorizationDeniedError):
        await service.create(
            _create(employee_id, payroll_run_id), _request_context(other_employee_id)
        )


async def test_get_missing_returns_none(service: PayslipService, employee_id: uuid.UUID):
    assert await service.get(uuid.uuid4(), _request_context(employee_id)) is None


async def test_get_denied_for_non_owner(
    service: PayslipService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    payslip = await service.create(
        _create(employee_id, payroll_run_id), _request_context(employee_id)
    )

    with pytest.raises(PayslipAuthorizationDeniedError):
        await service.get(payslip.id, _request_context(other_employee_id))


async def test_list_returns_created(
    service: PayslipService, employee_id: uuid.UUID, payroll_run_id: uuid.UUID
):
    context = _request_context(employee_id)
    await service.create(_create(employee_id, payroll_run_id), context)
    await service.create(_create(employee_id, payroll_run_id), context)

    items = await service.list(context)

    assert len(items) == 2
    assert {item.employee_id for item in items} == {employee_id}


async def test_list_returns_only_owned(
    service: PayslipService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    await service.create(_create(employee_id, payroll_run_id), _request_context(employee_id))
    await service.create(
        _create(other_employee_id, payroll_run_id), _request_context(other_employee_id)
    )

    items = await service.list(_request_context(employee_id))

    assert {item.employee_id for item in items} == {employee_id}
