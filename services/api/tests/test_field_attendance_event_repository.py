import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.core.field_attendance import FieldAttendanceEventType
from eop_api.db.base import Base
from eop_api.repositories.department import DepartmentRepository
from eop_api.repositories.employment_status import EmploymentStatusRepository
from eop_api.repositories.employment_type import EmploymentTypeRepository
from eop_api.repositories.field_attendance_event import FieldAttendanceEventRepository
from eop_api.repositories.file import FileRepository
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.job_grade import JobGradeRepository
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
def repo(session: AsyncSession) -> FieldAttendanceEventRepository:
    return FieldAttendanceEventRepository(session)


@pytest.fixture
async def employee_id(session: AsyncSession) -> uuid.UUID:
    organization = await OrganizationRepository(session).create(name="Acme Corp")
    department = await DepartmentRepository(session).create(
        organization_id=organization.id, code="ENG", name="Engineering"
    )
    position = await PositionRepository(session).create(
        organization_id=organization.id, department_id=department.id, code="ENG-1", name="Engineer"
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
async def selfie_file_id(session: AsyncSession) -> uuid.UUID:
    file_object = await FileRepository(session).create(
        filename="selfie.jpg",
        content_type="image/jpeg",
        size=1024,
        storage_key=f"selfies/{uuid.uuid4().hex}.jpg",
        bucket="eop-files",
    )
    return file_object.id


def _event_kwargs(employee_id: uuid.UUID, selfie_file_id: uuid.UUID, **overrides) -> dict:
    values = {
        "employee_id": employee_id,
        "event_type": FieldAttendanceEventType.CHECK_IN,
        "event_time": datetime(2026, 1, 5, 9, 0, tzinfo=UTC),
        "latitude": Decimal("-6.200000"),
        "longitude": Decimal("106.816666"),
        "gps_accuracy_meters": Decimal("12.50"),
        "selfie_file_id": selfie_file_id,
    }
    values.update(overrides)
    return values


async def test_create_and_get(
    repo: FieldAttendanceEventRepository, employee_id: uuid.UUID, selfie_file_id: uuid.UUID
):
    event = await repo.create(**_event_kwargs(employee_id, selfie_file_id))

    fetched = await repo.get(event.id)

    assert fetched is not None
    assert fetched.employee_id == employee_id
    assert fetched.event_type == FieldAttendanceEventType.CHECK_IN
    assert fetched.latitude == Decimal("-6.200000")
    assert fetched.longitude == Decimal("106.816666")
    assert fetched.gps_accuracy_meters == Decimal("12.50")
    assert fetched.selfie_file_id == selfie_file_id


async def test_get_missing_returns_none(repo: FieldAttendanceEventRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_multiple_events_per_employee_allowed(
    repo: FieldAttendanceEventRepository, employee_id: uuid.UUID, selfie_file_id: uuid.UUID
):
    first = await repo.create(**_event_kwargs(employee_id, selfie_file_id))
    second = await repo.create(
        **_event_kwargs(employee_id, selfie_file_id, event_type=FieldAttendanceEventType.CHECK_OUT)
    )

    assert first.id != second.id


async def test_update_existing(
    repo: FieldAttendanceEventRepository, employee_id: uuid.UUID, selfie_file_id: uuid.UUID
):
    event = await repo.create(**_event_kwargs(employee_id, selfie_file_id))

    updated = await repo.update(event.id, event_type=FieldAttendanceEventType.CHECK_OUT)

    assert updated is not None
    assert updated.event_type == FieldAttendanceEventType.CHECK_OUT


async def test_delete_existing(
    repo: FieldAttendanceEventRepository, employee_id: uuid.UUID, selfie_file_id: uuid.UUID
):
    event = await repo.create(**_event_kwargs(employee_id, selfie_file_id))

    deleted = await repo.delete(event.id)

    assert deleted is True
    assert await repo.get(event.id) is None


async def test_delete_missing_returns_false(repo: FieldAttendanceEventRepository):
    assert await repo.delete(uuid.uuid4()) is False


async def test_paginate_filters_by_event_type(
    repo: FieldAttendanceEventRepository, employee_id: uuid.UUID, selfie_file_id: uuid.UUID
):
    await repo.create(**_event_kwargs(employee_id, selfie_file_id))
    await repo.create(
        **_event_kwargs(employee_id, selfie_file_id, event_type=FieldAttendanceEventType.CHECK_OUT)
    )

    page = await repo.paginate(
        filters=FilterParams(values={"event_type": FieldAttendanceEventType.CHECK_IN})
    )
    assert page.total == 1

    other_page = await repo.paginate(filters=FilterParams(values={"employee_id": uuid.uuid4()}))
    assert other_page.total == 0


async def test_paginate_returns_total_and_page_slice(
    repo: FieldAttendanceEventRepository, employee_id: uuid.UUID, selfie_file_id: uuid.UUID
):
    for _ in range(5):
        await repo.create(**_event_kwargs(employee_id, selfie_file_id))

    page = await repo.paginate(offset=1, limit=2)

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2
