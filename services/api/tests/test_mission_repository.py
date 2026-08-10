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
from eop_api.repositories.mission import MissionRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.position import PositionRepository
from eop_api.repositories.shift import ShiftRepository
from eop_api.repositories.store import StoreRepository
from eop_api.repositories.store_type import StoreTypeRepository
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
def repo(session: AsyncSession) -> MissionRepository:
    return MissionRepository(session)


@pytest.fixture
async def ids(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    """An `HrEmployee.id` and a `Store.id`, each satisfying its own mandatory
    FKs -- Mission only needs the two ids to point at, not the rest of the
    chain."""
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

    store_type = await StoreTypeRepository(session).create(code="MT", name="Modern Trade")
    store = await StoreRepository(session).create(
        code="ST-1",
        name="Indomaret Sudirman",
        organization_id=organization.id,
        store_type_id=store_type.id,
    )

    return employee.id, store.id


async def test_create_and_get(repo: MissionRepository, ids: tuple[uuid.UUID, uuid.UUID]):
    employee_id, store_id = ids
    scheduled_date = date(2026, 1, 5)
    mission = await repo.create(
        employee_id=employee_id, store_id=store_id, scheduled_date=scheduled_date
    )

    fetched = await repo.get(mission.id)

    assert fetched is not None
    assert fetched.employee_id == employee_id
    assert fetched.store_id == store_id
    assert fetched.scheduled_date == scheduled_date


async def test_get_missing_returns_none(repo: MissionRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_multiple_missions_per_employee_and_store_allowed(
    repo: MissionRepository, ids: tuple[uuid.UUID, uuid.UUID]
):
    employee_id, store_id = ids
    first = await repo.create(
        employee_id=employee_id, store_id=store_id, scheduled_date=date(2026, 1, 5)
    )
    second = await repo.create(
        employee_id=employee_id, store_id=store_id, scheduled_date=date(2026, 1, 5)
    )

    assert first.id != second.id


async def test_update_existing(repo: MissionRepository, ids: tuple[uuid.UUID, uuid.UUID]):
    employee_id, store_id = ids
    mission = await repo.create(
        employee_id=employee_id, store_id=store_id, scheduled_date=date(2026, 1, 5)
    )

    updated = await repo.update(mission.id, scheduled_date=date(2026, 1, 12))

    assert updated is not None
    assert updated.scheduled_date == date(2026, 1, 12)


async def test_delete_existing(repo: MissionRepository, ids: tuple[uuid.UUID, uuid.UUID]):
    employee_id, store_id = ids
    mission = await repo.create(
        employee_id=employee_id, store_id=store_id, scheduled_date=date(2026, 1, 5)
    )

    deleted = await repo.delete(mission.id)

    assert deleted is True
    assert await repo.get(mission.id) is None


async def test_delete_missing_returns_false(repo: MissionRepository):
    assert await repo.delete(uuid.uuid4()) is False


async def test_paginate_filters_by_employee_id(
    repo: MissionRepository, ids: tuple[uuid.UUID, uuid.UUID]
):
    employee_id, store_id = ids
    mission = await repo.create(
        employee_id=employee_id, store_id=store_id, scheduled_date=date(2026, 1, 5)
    )

    page = await repo.paginate(filters=FilterParams(values={"employee_id": employee_id}))
    assert page.total == 1
    assert page.items[0].id == mission.id

    other_page = await repo.paginate(filters=FilterParams(values={"employee_id": uuid.uuid4()}))
    assert other_page.total == 0


async def test_paginate_filters_by_store_id(
    repo: MissionRepository, ids: tuple[uuid.UUID, uuid.UUID]
):
    employee_id, store_id = ids
    mission = await repo.create(
        employee_id=employee_id, store_id=store_id, scheduled_date=date(2026, 1, 5)
    )

    page = await repo.paginate(filters=FilterParams(values={"store_id": store_id}))
    assert page.total == 1
    assert page.items[0].id == mission.id


async def test_paginate_filters_by_scheduled_date(
    repo: MissionRepository, ids: tuple[uuid.UUID, uuid.UUID]
):
    employee_id, store_id = ids
    await repo.create(employee_id=employee_id, store_id=store_id, scheduled_date=date(2026, 1, 5))

    page = await repo.paginate(filters=FilterParams(values={"scheduled_date": date(2026, 1, 5)}))
    assert page.total == 1

    other_page = await repo.paginate(
        filters=FilterParams(values={"scheduled_date": date(2026, 1, 6)})
    )
    assert other_page.total == 0


async def test_paginate_returns_total_and_page_slice(
    repo: MissionRepository, ids: tuple[uuid.UUID, uuid.UUID]
):
    employee_id, store_id = ids
    for day in range(1, 6):
        await repo.create(
            employee_id=employee_id, store_id=store_id, scheduled_date=date(2026, 1, day)
        )

    page = await repo.paginate(offset=1, limit=2)

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2
