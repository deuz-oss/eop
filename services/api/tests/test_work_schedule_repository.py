import uuid
from collections.abc import AsyncGenerator
from datetime import date, datetime

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
from eop_api.repositories.position import PositionRepository
from eop_api.repositories.shift import ShiftRepository
from eop_api.repositories.team import TeamRepository
from eop_api.repositories.work_schedule import WorkScheduleRepository

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def connection() -> AsyncGenerator[AsyncConnection]:
    """A single connection with its own transaction, rolled back after the test."""
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
def repo(session: AsyncSession) -> WorkScheduleRepository:
    return WorkScheduleRepository(session)


@pytest.fixture
async def shift_id(session: AsyncSession) -> uuid.UUID:
    shift = await ShiftRepository(session).create(
        code="DAY",
        name="Day Shift",
        start_time=datetime(2024, 1, 1, 9, 0).time(),
        end_time=datetime(2024, 1, 1, 17, 0).time(),
    )
    return shift.id


@pytest.fixture
async def employee_id(session: AsyncSession, shift_id: uuid.UUID) -> uuid.UUID:
    """An `HrEmployee` row satisfying every mandatory FK it itself carries."""
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
        shift_id=shift_id,
        hire_date=datetime(2024, 1, 15).date(),
        employment_status="active",
    )
    return employee.id


def _week(**overrides: bool) -> dict[str, bool]:
    values = {
        "works_monday": True,
        "works_tuesday": True,
        "works_wednesday": True,
        "works_thursday": True,
        "works_friday": True,
        "works_saturday": False,
        "works_sunday": False,
    }
    values.update(overrides)
    return values


async def test_create_and_get(
    repo: WorkScheduleRepository, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    work_schedule = await repo.create(
        employee_id=employee_id,
        shift_id=shift_id,
        effective_from=date(2026, 1, 1),
        is_active=True,
        **_week(),
    )

    fetched = await repo.get(work_schedule.id)

    assert fetched is not None
    assert fetched.employee_id == employee_id
    assert fetched.shift_id == shift_id
    assert fetched.effective_from == date(2026, 1, 1)
    assert fetched.works_monday is True
    assert fetched.works_saturday is False
    assert fetched.is_active is True


async def test_get_missing_returns_none(repo: WorkScheduleRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_list_by_employee_id_returns_all_historical_rows(
    repo: WorkScheduleRepository, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    first = await repo.create(
        employee_id=employee_id,
        shift_id=shift_id,
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 6, 30),
        **_week(),
    )
    second = await repo.create(
        employee_id=employee_id, shift_id=shift_id, effective_from=date(2026, 7, 1), **_week()
    )

    history = await repo.list_by_employee_id(employee_id)

    assert [w.id for w in history] == [first.id, second.id]
    assert await repo.list_by_employee_id(uuid.uuid4()) == []


async def test_list_effective_as_of_before_effective_from_returns_empty(
    repo: WorkScheduleRepository, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    await repo.create(
        employee_id=employee_id, shift_id=shift_id, effective_from=date(2026, 1, 1), **_week()
    )

    assert await repo.list_effective_as_of(employee_id, date(2025, 12, 31)) == []


async def test_list_effective_as_of_inside_bounded_period(
    repo: WorkScheduleRepository, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    work_schedule = await repo.create(
        employee_id=employee_id,
        shift_id=shift_id,
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 6, 30),
        **_week(),
    )

    found = await repo.list_effective_as_of(employee_id, date(2026, 3, 15))

    assert [w.id for w in found] == [work_schedule.id]


async def test_list_effective_as_of_open_ended(
    repo: WorkScheduleRepository, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    work_schedule = await repo.create(
        employee_id=employee_id, shift_id=shift_id, effective_from=date(2026, 1, 1), **_week()
    )

    found = await repo.list_effective_as_of(employee_id, date(2099, 1, 1))

    assert [w.id for w in found] == [work_schedule.id]


async def test_list_effective_as_of_returns_both_correction_and_target(
    repo: WorkScheduleRepository, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    target = await repo.create(
        employee_id=employee_id,
        shift_id=shift_id,
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 6, 30),
        **_week(),
    )
    correction = await repo.create(
        employee_id=employee_id,
        shift_id=shift_id,
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 6, 30),
        corrects_id=target.id,
        **_week(works_saturday=True),
    )

    found = await repo.list_effective_as_of(employee_id, date(2026, 3, 1))

    assert {w.id for w in found} == {target.id, correction.id}


async def test_find_overlapping_periods_detects_bounded_overlap(
    repo: WorkScheduleRepository, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    existing = await repo.create(
        employee_id=employee_id,
        shift_id=shift_id,
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 6, 30),
        **_week(),
    )

    overlapping = await repo.find_overlapping_periods(
        employee_id, date(2026, 3, 1), date(2026, 9, 30)
    )

    assert [w.id for w in overlapping] == [existing.id]


async def test_find_overlapping_periods_no_overlap_returns_empty(
    repo: WorkScheduleRepository, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    await repo.create(
        employee_id=employee_id,
        shift_id=shift_id,
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 6, 30),
        **_week(),
    )

    overlapping = await repo.find_overlapping_periods(
        employee_id, date(2026, 7, 1), date(2026, 12, 31)
    )

    assert overlapping == []


async def test_find_overlapping_periods_excludes_correction_target(
    repo: WorkScheduleRepository, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    target = await repo.create(
        employee_id=employee_id,
        shift_id=shift_id,
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 6, 30),
        **_week(),
    )

    overlapping = await repo.find_overlapping_periods(
        employee_id, date(2026, 3, 1), date(2026, 6, 30), exclude_id=target.id
    )

    assert overlapping == []


async def test_find_overlapping_periods_scoped_to_employee(
    repo: WorkScheduleRepository, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    await repo.create(
        employee_id=employee_id, shift_id=shift_id, effective_from=date(2026, 1, 1), **_week()
    )

    overlapping = await repo.find_overlapping_periods(uuid.uuid4(), date(2026, 1, 1), None)

    assert overlapping == []


async def test_correction_row_retrievable_via_corrects_id(
    repo: WorkScheduleRepository, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    target = await repo.create(
        employee_id=employee_id,
        shift_id=shift_id,
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 6, 30),
        **_week(),
    )
    correction = await repo.create(
        employee_id=employee_id,
        shift_id=shift_id,
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 6, 30),
        corrects_id=target.id,
        **_week(),
    )

    fetched = await repo.get(correction.id)

    assert fetched is not None
    assert fetched.corrects_id == target.id


async def test_update_existing(
    repo: WorkScheduleRepository, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    work_schedule = await repo.create(
        employee_id=employee_id, shift_id=shift_id, effective_from=date(2026, 1, 1), **_week()
    )

    updated = await repo.update(work_schedule.id, is_active=False)

    assert updated is not None
    assert updated.is_active is False


async def test_delete_existing(
    repo: WorkScheduleRepository, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    work_schedule = await repo.create(
        employee_id=employee_id, shift_id=shift_id, effective_from=date(2026, 1, 1), **_week()
    )

    deleted = await repo.delete(work_schedule.id)

    assert deleted is True
    assert await repo.get(work_schedule.id) is None
