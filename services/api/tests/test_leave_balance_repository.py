import uuid
from collections.abc import AsyncGenerator
from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError
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
from eop_api.repositories.leave_balance import LeaveBalanceRepository
from eop_api.repositories.location import LocationRepository
from eop_api.repositories.location_type import LocationTypeRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.position import PositionRepository
from eop_api.repositories.shift import ShiftRepository
from eop_api.repositories.team import TeamRepository
from eop_api.schemas.search import FilterParams

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
def repo(session: AsyncSession) -> LeaveBalanceRepository:
    return LeaveBalanceRepository(session)


@pytest.fixture
async def employee_id(session: AsyncSession) -> uuid.UUID:
    """An `HrEmployee` row satisfying every mandatory FK it itself carries.

    LeaveBalance only needs a valid `HrEmployee.id` to point at -- the full
    Organization/Department/Position/Team/Location/JobGrade/EmploymentType/
    EmploymentStatus/Shift chain below exists solely because `HrEmployee`
    requires it, not because LeaveBalance cares about any of it.
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


async def test_create_and_get(repo: LeaveBalanceRepository, employee_id: uuid.UUID):
    leave_balance = await repo.create(
        employee_id=employee_id,
        period_year=2026,
        allocated_days=12,
        used_days=2,
        remaining_days=10,
    )

    fetched = await repo.get(leave_balance.id)

    assert fetched is not None
    assert fetched.employee_id == employee_id
    assert fetched.period_year == 2026
    assert fetched.allocated_days == 12
    assert fetched.used_days == 2
    assert fetched.remaining_days == 10


async def test_create_defaults(repo: LeaveBalanceRepository, employee_id: uuid.UUID):
    leave_balance = await repo.create(employee_id=employee_id, period_year=2026)

    assert leave_balance.allocated_days == 0
    assert leave_balance.used_days == 0
    assert leave_balance.remaining_days == 0


async def test_get_missing_returns_none(repo: LeaveBalanceRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_list_returns_created(repo: LeaveBalanceRepository, employee_id: uuid.UUID):
    await repo.create(employee_id=employee_id, period_year=2025)
    await repo.create(employee_id=employee_id, period_year=2026)

    items = await repo.list()

    assert {2025, 2026}.issubset({item.period_year for item in items})


async def test_get_by_employee_returns_only_that_employees_balances(
    repo: LeaveBalanceRepository, session: AsyncSession, employee_id: uuid.UUID
):
    other_organization = await OrganizationRepository(session).create(name="Other Corp")
    other_department = await DepartmentRepository(session).create(
        organization_id=other_organization.id, code="SLS", name="Sales"
    )
    other_position = await PositionRepository(session).create(
        organization_id=other_organization.id,
        department_id=other_department.id,
        code="SLS-1",
        name="Salesperson",
    )
    other_team = await TeamRepository(session).create(
        organization_id=other_organization.id,
        department_id=other_department.id,
        code="FIELD",
        name="Field Team",
    )
    location_type = await LocationTypeRepository(session).create(code="REMOTE", name="Remote")
    location = await LocationRepository(session).create(
        code="RMT", name="Remote", location_type_id=location_type.id
    )
    job_grade = await JobGradeRepository(session).create(code="L2", name="Mid", level=2)
    employment_type = await EmploymentTypeRepository(session).create(code="PT", name="Part-Time")
    employment_status = await EmploymentStatusRepository(session).create(
        code="ACTIVE2", name="Active"
    )
    shift = await ShiftRepository(session).create(
        code="NIGHT",
        name="Night Shift",
        start_time=datetime(2024, 1, 1, 22, 0).time(),
        end_time=datetime(2024, 1, 2, 6, 0).time(),
    )
    other_employee = await HrEmployeeRepository(session).create(
        employee_number="EMP-2",
        first_name="Grace",
        last_name="Hopper",
        full_name="Grace Hopper",
        email="grace@example.com",
        organization_id=other_organization.id,
        department_id=other_department.id,
        position_id=other_position.id,
        team_id=other_team.id,
        location_id=location.id,
        job_grade_id=job_grade.id,
        employment_type_id=employment_type.id,
        employment_status_id=employment_status.id,
        shift_id=shift.id,
        hire_date=datetime(2024, 1, 15).date(),
        employment_status="active",
    )

    mine = await repo.create(employee_id=employee_id, period_year=2026)
    await repo.create(employee_id=other_employee.id, period_year=2026)

    items = await repo.get_by_employee(employee_id)

    assert [item.id for item in items] == [mine.id]


async def test_get_by_employee_and_period_year_returns_matching_row(
    repo: LeaveBalanceRepository, employee_id: uuid.UUID
):
    balance = await repo.create(employee_id=employee_id, period_year=2026)

    items = await repo.get_by_employee_and_period_year(employee_id, 2026)

    assert [item.id for item in items] == [balance.id]


async def test_get_by_employee_and_period_year_excludes_different_year(
    repo: LeaveBalanceRepository, employee_id: uuid.UUID
):
    await repo.create(employee_id=employee_id, period_year=2026)

    items = await repo.get_by_employee_and_period_year(employee_id, 2027)

    assert items == []


async def test_get_by_employee_and_period_year_excludes_different_employee(
    repo: LeaveBalanceRepository, session: AsyncSession, employee_id: uuid.UUID
):
    other_organization = await OrganizationRepository(session).create(name="Other Corp")
    other_department = await DepartmentRepository(session).create(
        organization_id=other_organization.id, code="SLS", name="Sales"
    )
    other_position = await PositionRepository(session).create(
        organization_id=other_organization.id,
        department_id=other_department.id,
        code="SLS-1",
        name="Salesperson",
    )
    other_team = await TeamRepository(session).create(
        organization_id=other_organization.id,
        department_id=other_department.id,
        code="FIELD",
        name="Field Team",
    )
    location_type = await LocationTypeRepository(session).create(code="REMOTE", name="Remote")
    location = await LocationRepository(session).create(
        code="RMT", name="Remote", location_type_id=location_type.id
    )
    job_grade = await JobGradeRepository(session).create(code="L2", name="Mid", level=2)
    employment_type = await EmploymentTypeRepository(session).create(code="PT", name="Part-Time")
    employment_status = await EmploymentStatusRepository(session).create(
        code="ACTIVE2", name="Active"
    )
    shift = await ShiftRepository(session).create(
        code="NIGHT",
        name="Night Shift",
        start_time=datetime(2024, 1, 1, 22, 0).time(),
        end_time=datetime(2024, 1, 2, 6, 0).time(),
    )
    other_employee = await HrEmployeeRepository(session).create(
        employee_number="EMP-2",
        first_name="Grace",
        last_name="Hopper",
        full_name="Grace Hopper",
        email="grace2@example.com",
        organization_id=other_organization.id,
        department_id=other_department.id,
        position_id=other_position.id,
        team_id=other_team.id,
        location_id=location.id,
        job_grade_id=job_grade.id,
        employment_type_id=employment_type.id,
        employment_status_id=employment_status.id,
        shift_id=shift.id,
        hire_date=datetime(2024, 1, 15).date(),
        employment_status="active",
    )

    mine = await repo.create(employee_id=employee_id, period_year=2026)
    await repo.create(employee_id=other_employee.id, period_year=2026)

    items = await repo.get_by_employee_and_period_year(employee_id, 2026)

    assert [item.id for item in items] == [mine.id]


async def test_get_by_employee_and_period_year_returns_multiple_rows(
    repo: LeaveBalanceRepository, employee_id: uuid.UUID
):
    """No uniqueness constraint on `(employee_id, period_year)` in v1 -- if
    more than one row matches, all of them are returned as a `Sequence`."""
    first = await repo.create(employee_id=employee_id, period_year=2026)
    second = await repo.create(employee_id=employee_id, period_year=2026)

    items = await repo.get_by_employee_and_period_year(employee_id, 2026)

    assert {item.id for item in items} == {first.id, second.id}


async def test_update_existing(repo: LeaveBalanceRepository, employee_id: uuid.UUID):
    leave_balance = await repo.create(employee_id=employee_id, period_year=2026)

    updated = await repo.update(leave_balance.id, used_days=3, remaining_days=9)

    assert updated is not None
    assert updated.used_days == 3
    assert updated.remaining_days == 9


async def test_update_missing_returns_none(repo: LeaveBalanceRepository):
    assert await repo.update(uuid.uuid4(), used_days=3) is None


async def test_delete_existing(repo: LeaveBalanceRepository, employee_id: uuid.UUID):
    leave_balance = await repo.create(employee_id=employee_id, period_year=2026)

    deleted = await repo.delete(leave_balance.id)

    assert deleted is True
    assert await repo.get(leave_balance.id) is None


async def test_delete_missing_returns_false(repo: LeaveBalanceRepository):
    assert await repo.delete(uuid.uuid4()) is False


async def test_delete_employee_referenced_by_leave_balance_is_restricted(
    repo: LeaveBalanceRepository, session: AsyncSession, employee_id: uuid.UUID
):
    await repo.create(employee_id=employee_id, period_year=2026)

    with pytest.raises(IntegrityError):
        await HrEmployeeRepository(session).delete(employee_id)


async def test_paginate_returns_total_and_page_slice(
    repo: LeaveBalanceRepository, employee_id: uuid.UUID
):
    for i in range(5):
        await repo.create(employee_id=employee_id, period_year=2022 + i)

    page = await repo.paginate(offset=1, limit=2)

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_paginate_defaults(repo: LeaveBalanceRepository, employee_id: uuid.UUID):
    for i in range(3):
        await repo.create(employee_id=employee_id, period_year=2024 + i)

    page = await repo.paginate()

    assert page.offset == 0
    assert page.limit == 50
    assert page.total == 3
    assert len(page.items) == 3


async def test_paginate_filters_by_employee_id(
    repo: LeaveBalanceRepository, employee_id: uuid.UUID
):
    leave_balance = await repo.create(employee_id=employee_id, period_year=2026)

    page = await repo.paginate(filters=FilterParams(values={"employee_id": employee_id}))

    assert page.total == 1
    assert page.items[0].id == leave_balance.id


async def test_paginate_filters_by_period_year(
    repo: LeaveBalanceRepository, employee_id: uuid.UUID
):
    matching = await repo.create(employee_id=employee_id, period_year=2026)
    await repo.create(employee_id=employee_id, period_year=2027)

    page = await repo.paginate(filters=FilterParams(values={"period_year": 2026}))

    assert page.total == 1
    assert page.items[0].id == matching.id


async def test_paginate_without_filters_returns_all_rows(
    repo: LeaveBalanceRepository, employee_id: uuid.UUID
):
    await repo.create(employee_id=employee_id, period_year=2026)
    await repo.create(employee_id=employee_id, period_year=2027)

    page = await repo.paginate()

    assert page.total == 2
