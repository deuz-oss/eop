import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import date, datetime

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
from eop_api.repositories.position import PositionRepository
from eop_api.repositories.shift import ShiftRepository
from eop_api.repositories.store import StoreRepository
from eop_api.repositories.store_type import StoreTypeRepository
from eop_api.repositories.team import TeamRepository
from eop_api.schemas.mission import MissionCreate, MissionUpdate
from eop_api.services.mission import EmployeeNotFoundError, MissionService, StoreNotFoundError
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
                    "store_types CASCADE"
                )
            )
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> MissionService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return MissionService(uow_factory)


async def _create_ids(
    session_factory: Callable[[], AsyncSession], *, suffix: str
) -> tuple[uuid.UUID, uuid.UUID]:
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
            code=f"L1-{suffix}", name="Junior", level=int(suffix[-1])
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
        store_type = await StoreTypeRepository(session).create(
            code=f"MT-{suffix}", name="Modern Trade"
        )
        store = await StoreRepository(session).create(
            code=f"ST-{suffix}",
            name="Indomaret Sudirman",
            organization_id=organization.id,
            store_type_id=store_type.id,
        )
        await session.commit()
        return employee.id, store.id


@pytest.fixture
async def ids(session_factory: Callable[[], AsyncSession]) -> tuple[uuid.UUID, uuid.UUID]:
    return await _create_ids(session_factory, suffix="e1")


def _create(employee_id: uuid.UUID, store_id: uuid.UUID, **overrides) -> MissionCreate:
    values = {"employee_id": employee_id, "store_id": store_id, "scheduled_date": date(2026, 1, 5)}
    values.update(overrides)
    return MissionCreate(**values)


async def test_create_and_get(service: MissionService, ids: tuple[uuid.UUID, uuid.UUID]):
    employee_id, store_id = ids
    mission = await service.create(_create(employee_id, store_id))

    fetched = await service.get(mission.id)

    assert fetched is not None
    assert fetched.employee_id == employee_id
    assert fetched.store_id == store_id
    assert fetched.scheduled_date == date(2026, 1, 5)


async def test_create_rejects_missing_employee(
    service: MissionService, ids: tuple[uuid.UUID, uuid.UUID]
):
    _, store_id = ids
    with pytest.raises(EmployeeNotFoundError):
        await service.create(_create(uuid.uuid4(), store_id))


async def test_create_rejects_missing_store(
    service: MissionService, ids: tuple[uuid.UUID, uuid.UUID]
):
    employee_id, _ = ids
    with pytest.raises(StoreNotFoundError):
        await service.create(_create(employee_id, uuid.uuid4()))


async def test_create_allows_duplicate_employee_store_date(
    service: MissionService, ids: tuple[uuid.UUID, uuid.UUID]
):
    employee_id, store_id = ids
    first = await service.create(_create(employee_id, store_id))
    second = await service.create(_create(employee_id, store_id))

    assert first.id != second.id


async def test_get_missing_returns_none(service: MissionService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(service: MissionService, ids: tuple[uuid.UUID, uuid.UUID]):
    employee_id, store_id = ids
    await service.create(_create(employee_id, store_id, scheduled_date=date(2026, 1, 5)))
    await service.create(_create(employee_id, store_id, scheduled_date=date(2026, 1, 6)))

    items = await service.list()

    assert {item.scheduled_date for item in items} == {date(2026, 1, 5), date(2026, 1, 6)}


async def test_update_employee_id(
    service: MissionService,
    session_factory: Callable[[], AsyncSession],
    ids: tuple[uuid.UUID, uuid.UUID],
):
    employee_id, store_id = ids
    mission = await service.create(_create(employee_id, store_id))

    other_employee_id, _ = await _create_ids(session_factory, suffix="e2")
    updated = await service.update(mission.id, MissionUpdate(employee_id=other_employee_id))

    assert updated is not None
    assert updated.employee_id == other_employee_id
    assert updated.store_id == store_id


async def test_update_store_id(
    service: MissionService,
    session_factory: Callable[[], AsyncSession],
    ids: tuple[uuid.UUID, uuid.UUID],
):
    employee_id, store_id = ids
    mission = await service.create(_create(employee_id, store_id))

    _, other_store_id = await _create_ids(session_factory, suffix="e3")
    updated = await service.update(mission.id, MissionUpdate(store_id=other_store_id))

    assert updated is not None
    assert updated.store_id == other_store_id
    assert updated.employee_id == employee_id


async def test_update_scheduled_date(service: MissionService, ids: tuple[uuid.UUID, uuid.UUID]):
    employee_id, store_id = ids
    mission = await service.create(_create(employee_id, store_id))

    updated = await service.update(mission.id, MissionUpdate(scheduled_date=date(2026, 2, 1)))

    assert updated is not None
    assert updated.scheduled_date == date(2026, 2, 1)


async def test_update_rejects_missing_employee(
    service: MissionService, ids: tuple[uuid.UUID, uuid.UUID]
):
    employee_id, store_id = ids
    mission = await service.create(_create(employee_id, store_id))

    with pytest.raises(EmployeeNotFoundError):
        await service.update(mission.id, MissionUpdate(employee_id=uuid.uuid4()))


async def test_update_rejects_missing_store(
    service: MissionService, ids: tuple[uuid.UUID, uuid.UUID]
):
    employee_id, store_id = ids
    mission = await service.create(_create(employee_id, store_id))

    with pytest.raises(StoreNotFoundError):
        await service.update(mission.id, MissionUpdate(store_id=uuid.uuid4()))


async def test_update_missing_returns_none(service: MissionService):
    assert (
        await service.update(uuid.uuid4(), MissionUpdate(scheduled_date=date(2026, 1, 1))) is None
    )


async def test_delete_existing(service: MissionService, ids: tuple[uuid.UUID, uuid.UUID]):
    employee_id, store_id = ids
    mission = await service.create(_create(employee_id, store_id))

    deleted = await service.delete(mission.id)

    assert deleted is True
    assert await service.get(mission.id) is None


async def test_delete_missing_returns_false(service: MissionService):
    assert await service.delete(uuid.uuid4()) is False
