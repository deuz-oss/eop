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
from eop_api.schemas.deduction import DeductionCreate, DeductionUpdate
from eop_api.schemas.deduction_type import DeductionTypeCreate
from eop_api.services.deduction import (
    DeductionAuthorizationDeniedError,
    DeductionService,
    DeductionTypeNotFoundError,
    EmployeeNotFoundError,
    PayrollRunCompletedError,
    PayrollRunNotFoundError,
)
from eop_api.services.deduction_type import DeductionTypeService
from eop_api.services.employee_context import EmployeeContext, RequestContext
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
                    "payroll_runs, deduction_types CASCADE"
                )
            )
        await engine.dispose()


@pytest.fixture
def uow_factory(
    session_factory: Callable[[], AsyncSession],
) -> Callable[[], SQLAlchemyUnitOfWork]:
    return lambda: SQLAlchemyUnitOfWork(session_factory)  # noqa: E731


@pytest.fixture
def service(uow_factory: Callable[[], SQLAlchemyUnitOfWork]) -> DeductionService:
    return DeductionService(uow_factory)


@pytest.fixture
def deduction_type_service(
    uow_factory: Callable[[], SQLAlchemyUnitOfWork],
) -> DeductionTypeService:
    return DeductionTypeService(uow_factory)


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
            code=f"L1-{suffix}", name="Junior", level=1
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
async def payroll_run_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
    async with session_factory() as session:
        payroll_run = await PayrollRunRepository(session).create(
            code="RUN-001",
            name="First Run",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            currency="IDR",
        )
        await session.commit()
        return payroll_run.id


@pytest.fixture
async def deduction_type_id(deduction_type_service: DeductionTypeService) -> uuid.UUID:
    deduction_type = await deduction_type_service.create(
        DeductionTypeCreate(code="LOAN", name="Loan Repayment")
    )
    return deduction_type.id


def _request_context(employee_id: uuid.UUID) -> RequestContext:
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


def _create(
    employee_id: uuid.UUID, deduction_type_id: uuid.UUID, payroll_run_id: uuid.UUID, **overrides
) -> DeductionCreate:
    values = {
        "employee_id": employee_id,
        "deduction_type_id": deduction_type_id,
        "payroll_run_id": payroll_run_id,
        "deduction_amount": Decimal("100000.00"),
        "deduction_currency": "IDR",
    }
    values.update(overrides)
    return DeductionCreate(**values)


async def test_create_and_list_by_employee(
    service: DeductionService,
    employee_id: uuid.UUID,
    deduction_type_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    await service.create(_create(employee_id, deduction_type_id, payroll_run_id))

    items = await service.list_by_employee(_request_context(employee_id))

    assert len(items) == 1
    assert items[0].deduction_amount == Decimal("100000.00")


async def test_create_rejects_missing_employee(
    service: DeductionService, deduction_type_id: uuid.UUID, payroll_run_id: uuid.UUID
):
    with pytest.raises(EmployeeNotFoundError):
        await service.create(_create(uuid.uuid4(), deduction_type_id, payroll_run_id))


async def test_create_rejects_missing_deduction_type(
    service: DeductionService, employee_id: uuid.UUID, payroll_run_id: uuid.UUID
):
    with pytest.raises(DeductionTypeNotFoundError):
        await service.create(_create(employee_id, uuid.uuid4(), payroll_run_id))


async def test_create_rejects_missing_payroll_run(
    service: DeductionService, employee_id: uuid.UUID, deduction_type_id: uuid.UUID
):
    with pytest.raises(PayrollRunNotFoundError):
        await service.create(_create(employee_id, deduction_type_id, uuid.uuid4()))


async def test_create_rejects_completed_payroll_run(
    service: DeductionService,
    employee_id: uuid.UUID,
    deduction_type_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
    session_factory: Callable[[], AsyncSession],
):
    async with session_factory() as session:
        await PayrollRunRepository(session).update(
            payroll_run_id, status=PayrollRunStatus.COMPLETED
        )
        await session.commit()

    with pytest.raises(PayrollRunCompletedError):
        await service.create(_create(employee_id, deduction_type_id, payroll_run_id))


async def test_get_denied_for_non_owner(
    service: DeductionService,
    employee_id: uuid.UUID,
    deduction_type_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    deduction = await service.create(_create(employee_id, deduction_type_id, payroll_run_id))

    with pytest.raises(DeductionAuthorizationDeniedError):
        await service.get(deduction.id, _request_context(uuid.uuid4()))


async def test_update_existing(
    service: DeductionService,
    employee_id: uuid.UUID,
    deduction_type_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    deduction = await service.create(_create(employee_id, deduction_type_id, payroll_run_id))

    updated = await service.update(
        deduction.id, DeductionUpdate(deduction_amount=Decimal("150000.00"))
    )

    assert updated is not None
    assert updated.deduction_amount == Decimal("150000.00")


async def test_update_rejects_completed_payroll_run(
    service: DeductionService,
    employee_id: uuid.UUID,
    deduction_type_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
    session_factory: Callable[[], AsyncSession],
):
    deduction = await service.create(_create(employee_id, deduction_type_id, payroll_run_id))
    async with session_factory() as session:
        await PayrollRunRepository(session).update(
            payroll_run_id, status=PayrollRunStatus.COMPLETED
        )
        await session.commit()

    with pytest.raises(PayrollRunCompletedError):
        await service.update(deduction.id, DeductionUpdate(deduction_amount=Decimal("1.00")))


async def test_delete_existing(
    service: DeductionService,
    employee_id: uuid.UUID,
    deduction_type_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    deduction = await service.create(_create(employee_id, deduction_type_id, payroll_run_id))

    deleted = await service.delete(deduction.id)

    assert deleted is True


async def test_delete_rejects_completed_payroll_run(
    service: DeductionService,
    employee_id: uuid.UUID,
    deduction_type_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
    session_factory: Callable[[], AsyncSession],
):
    deduction = await service.create(_create(employee_id, deduction_type_id, payroll_run_id))
    async with session_factory() as session:
        await PayrollRunRepository(session).update(
            payroll_run_id, status=PayrollRunStatus.COMPLETED
        )
        await session.commit()

    with pytest.raises(PayrollRunCompletedError):
        await service.delete(deduction.id)


async def test_list_by_employee_and_payroll_run(
    service: DeductionService,
    employee_id: uuid.UUID,
    deduction_type_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    await service.create(_create(employee_id, deduction_type_id, payroll_run_id))

    items = await service.list_by_employee_and_payroll_run(employee_id, payroll_run_id)

    assert len(items) == 1
