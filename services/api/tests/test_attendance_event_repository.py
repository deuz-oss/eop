import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.attendance import EventSource, EventType
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.repositories.attendance_event import AttendanceEventRepository
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
from eop_api.schemas.search import FilterParams, SearchParams

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
def repo(session: AsyncSession) -> AttendanceEventRepository:
    return AttendanceEventRepository(session)


@pytest.fixture
async def employee_id(session: AsyncSession) -> uuid.UUID:
    """An `HrEmployee` row satisfying every mandatory FK it itself carries.

    Attendance only needs a valid `HrEmployee.id` to point at -- the full
    Organization/Department/Position/Team/Location/JobGrade/EmploymentType/
    EmploymentStatus/Shift chain below exists solely because `HrEmployee`
    requires it, not because Attendance cares about any of it.
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
async def shift_id(session: AsyncSession) -> uuid.UUID:
    shift = await ShiftRepository(session).create(
        code="NIGHT",
        name="Night Shift",
        start_time=datetime(2024, 1, 1, 22, 0).time(),
        end_time=datetime(2024, 1, 1, 6, 0).time(),
    )
    return shift.id


async def test_create_and_get(
    repo: AttendanceEventRepository, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    event_time = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)
    event = await repo.create(
        employee_id=employee_id,
        shift_id=shift_id,
        event_type=EventType.CLOCK_IN,
        event_time=event_time,
        source=EventSource.SYSTEM,
    )

    fetched = await repo.get(event.id)

    assert fetched is not None
    assert fetched.employee_id == employee_id
    assert fetched.shift_id == shift_id
    assert fetched.event_type == EventType.CLOCK_IN
    assert fetched.event_time == event_time
    assert fetched.source == EventSource.SYSTEM
    assert fetched.remarks is None


async def test_get_missing_returns_none(repo: AttendanceEventRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_list_returns_created(
    repo: AttendanceEventRepository, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    await repo.create(
        employee_id=employee_id,
        shift_id=shift_id,
        event_type=EventType.CLOCK_IN,
        event_time=datetime(2026, 1, 5, 9, 0, tzinfo=UTC),
        source=EventSource.SYSTEM,
    )
    await repo.create(
        employee_id=employee_id,
        shift_id=shift_id,
        event_type=EventType.CLOCK_OUT,
        event_time=datetime(2026, 1, 5, 17, 0, tzinfo=UTC),
        source=EventSource.SYSTEM,
    )

    items = await repo.list()

    assert {EventType.CLOCK_IN, EventType.CLOCK_OUT}.issubset({item.event_type for item in items})


async def test_update_existing(
    repo: AttendanceEventRepository, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    event = await repo.create(
        employee_id=employee_id,
        shift_id=shift_id,
        event_type=EventType.CLOCK_IN,
        event_time=datetime(2026, 1, 5, 9, 0, tzinfo=UTC),
        source=EventSource.SYSTEM,
    )

    updated = await repo.update(event.id, remarks="Corrected")

    assert updated is not None
    assert updated.remarks == "Corrected"


async def test_update_missing_returns_none(repo: AttendanceEventRepository):
    assert await repo.update(uuid.uuid4(), remarks="Corrected") is None


async def test_delete_existing(
    repo: AttendanceEventRepository, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    event = await repo.create(
        employee_id=employee_id,
        shift_id=shift_id,
        event_type=EventType.CLOCK_IN,
        event_time=datetime(2026, 1, 5, 9, 0, tzinfo=UTC),
        source=EventSource.SYSTEM,
    )

    deleted = await repo.delete(event.id)

    assert deleted is True
    assert await repo.get(event.id) is None


async def test_delete_missing_returns_false(repo: AttendanceEventRepository):
    assert await repo.delete(uuid.uuid4()) is False


async def test_create_persists_corrects_id(
    repo: AttendanceEventRepository, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    """Persistence-only: `corrects_id` round-trips like any other column --
    lineage validation (AttendanceEvent Integrity workstream) is
    `AttendanceEventService`'s job, not this repository's."""
    original = await repo.create(
        employee_id=employee_id,
        shift_id=shift_id,
        event_type=EventType.CLOCK_IN,
        event_time=datetime(2026, 1, 5, 9, 0, tzinfo=UTC),
        source=EventSource.SYSTEM,
    )

    correction = await repo.create(
        employee_id=employee_id,
        shift_id=shift_id,
        event_type=EventType.CLOCK_IN,
        event_time=datetime(2026, 1, 5, 9, 5, tzinfo=UTC),
        source=EventSource.MANUAL,
        corrects_id=original.id,
    )

    fetched = await repo.get(correction.id)
    assert fetched is not None
    assert fetched.corrects_id == original.id

    fetched_original = await repo.get(original.id)
    assert fetched_original is not None
    assert fetched_original.corrects_id is None


async def test_paginate_returns_total_and_page_slice(
    repo: AttendanceEventRepository, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    for i in range(5):
        await repo.create(
            employee_id=employee_id,
            shift_id=shift_id,
            event_type=EventType.CLOCK_IN,
            event_time=datetime(2026, 1, 5, 9, i, tzinfo=UTC),
            source=EventSource.SYSTEM,
        )

    page = await repo.paginate(offset=1, limit=2)

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_paginate_defaults(
    repo: AttendanceEventRepository, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    for i in range(3):
        await repo.create(
            employee_id=employee_id,
            shift_id=shift_id,
            event_type=EventType.CLOCK_IN,
            event_time=datetime(2026, 1, 5, 9, i, tzinfo=UTC),
            source=EventSource.SYSTEM,
        )

    page = await repo.paginate()

    assert page.offset == 0
    assert page.limit == 50
    assert page.total == 3
    assert len(page.items) == 3


async def test_paginate_search_returns_matching_rows_by_remarks(
    repo: AttendanceEventRepository, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    await repo.create(
        employee_id=employee_id,
        shift_id=shift_id,
        event_type=EventType.CLOCK_IN,
        event_time=datetime(2026, 1, 5, 9, 0, tzinfo=UTC),
        source=EventSource.SYSTEM,
        remarks="Late due to traffic",
    )
    await repo.create(
        employee_id=employee_id,
        shift_id=shift_id,
        event_type=EventType.CLOCK_OUT,
        event_time=datetime(2026, 1, 5, 17, 0, tzinfo=UTC),
        source=EventSource.SYSTEM,
        remarks="On time",
    )

    page = await repo.paginate(search=SearchParams(q="traffic"))

    assert page.total == 1
    assert page.items[0].remarks == "Late due to traffic"


async def test_paginate_no_search_returns_all_rows(
    repo: AttendanceEventRepository, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    await repo.create(
        employee_id=employee_id,
        shift_id=shift_id,
        event_type=EventType.CLOCK_IN,
        event_time=datetime(2026, 1, 5, 9, 0, tzinfo=UTC),
        source=EventSource.SYSTEM,
    )
    await repo.create(
        employee_id=employee_id,
        shift_id=shift_id,
        event_type=EventType.CLOCK_OUT,
        event_time=datetime(2026, 1, 5, 17, 0, tzinfo=UTC),
        source=EventSource.SYSTEM,
    )

    page = await repo.paginate(search=None)

    assert page.total == 2


async def test_paginate_filters_by_event_type(
    repo: AttendanceEventRepository, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    clock_in = await repo.create(
        employee_id=employee_id,
        shift_id=shift_id,
        event_type=EventType.CLOCK_IN,
        event_time=datetime(2026, 1, 5, 9, 0, tzinfo=UTC),
        source=EventSource.SYSTEM,
    )
    await repo.create(
        employee_id=employee_id,
        shift_id=shift_id,
        event_type=EventType.CLOCK_OUT,
        event_time=datetime(2026, 1, 5, 17, 0, tzinfo=UTC),
        source=EventSource.SYSTEM,
    )

    page = await repo.paginate(filters=FilterParams(values={"event_type": EventType.CLOCK_IN}))

    assert page.total == 1
    assert page.items[0].id == clock_in.id


async def test_paginate_filters_by_employee_id(
    repo: AttendanceEventRepository,
    session: AsyncSession,
    employee_id: uuid.UUID,
    shift_id: uuid.UUID,
):
    event = await repo.create(
        employee_id=employee_id,
        shift_id=shift_id,
        event_type=EventType.CLOCK_IN,
        event_time=datetime(2026, 1, 5, 9, 0, tzinfo=UTC),
        source=EventSource.SYSTEM,
    )

    page = await repo.paginate(filters=FilterParams(values={"employee_id": employee_id}))

    assert page.total == 1
    assert page.items[0].id == event.id


async def test_paginate_without_filters_returns_all_rows(
    repo: AttendanceEventRepository, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    await repo.create(
        employee_id=employee_id,
        shift_id=shift_id,
        event_type=EventType.CLOCK_IN,
        event_time=datetime(2026, 1, 5, 9, 0, tzinfo=UTC),
        source=EventSource.SYSTEM,
    )
    await repo.create(
        employee_id=employee_id,
        shift_id=shift_id,
        event_type=EventType.CLOCK_OUT,
        event_time=datetime(2026, 1, 5, 17, 0, tzinfo=UTC),
        source=EventSource.SYSTEM,
    )

    page = await repo.paginate()

    assert page.total == 2
