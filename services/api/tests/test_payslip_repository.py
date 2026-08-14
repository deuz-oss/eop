import uuid
from collections.abc import AsyncGenerator
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

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
from eop_api.repositories.payslip import PayslipRepository
from eop_api.repositories.position import PositionRepository
from eop_api.repositories.shift import ShiftRepository
from eop_api.repositories.team import TeamRepository

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def connection() -> AsyncGenerator[AsyncConnection]:
    """A single connection with its own transaction, rolled back after the test.

    The tables are real, migration-managed tables shared with the running
    application, so tests must never commit or drop them. Everything a test does
    happens inside one uncommitted transaction that is discarded on teardown.
    """
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    conn = await engine.connect()
    trans = await conn.begin()
    try:
        yield conn
    finally:
        await trans.rollback()
        await conn.close()
        await engine.dispose()


@pytest.fixture
def session(connection: AsyncConnection) -> AsyncSession:
    return async_sessionmaker(bind=connection, expire_on_commit=False)()


@pytest.fixture
def repo(session: AsyncSession) -> PayslipRepository:
    return PayslipRepository(session)


@pytest.fixture
async def employee_id(session: AsyncSession) -> uuid.UUID:
    """An `HrEmployee` row satisfying every mandatory FK it itself carries.

    Payslip only needs a valid `HrEmployee.id` to point at -- the full
    Organization/Department/Position/Team/Location/JobGrade/EmploymentType/
    EmploymentStatus/Shift chain below exists solely because `HrEmployee`
    requires it, mirroring `test_attendance_event_repository.py`'s fixture.
    """
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
    location_type = await LocationTypeRepository(session).create(code="OFFICE", name="Office")
    location = await LocationRepository(session).create(
        code="HQ", name="HQ", location_type_id=location_type.id
    )
    job_grade = await JobGradeRepository(session).create(code="L1", name="Junior", level=1)
    employment_type = await EmploymentTypeRepository(session).create(code="FT", name="Full-Time")
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
    return employee.id


@pytest.fixture
async def payroll_run_id(session: AsyncSession) -> uuid.UUID:
    payroll_run = await PayrollRunRepository(session).create(code="RUN-001", name="First Run")
    return payroll_run.id


async def test_create_and_get(
    repo: PayslipRepository, employee_id: uuid.UUID, payroll_run_id: uuid.UUID
):
    payslip = await repo.create(employee_id=employee_id, payroll_run_id=payroll_run_id)

    fetched = await repo.get(payslip.id)

    assert fetched is not None
    assert fetched.employee_id == employee_id
    assert fetched.payroll_run_id == payroll_run_id


async def test_get_missing_returns_none(repo: PayslipRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_list_returns_created(
    repo: PayslipRepository, employee_id: uuid.UUID, payroll_run_id: uuid.UUID
):
    await repo.create(employee_id=employee_id, payroll_run_id=payroll_run_id)
    await repo.create(employee_id=employee_id, payroll_run_id=payroll_run_id)

    items = await repo.list()

    assert len(items) == 2
    assert {item.employee_id for item in items} == {employee_id}
