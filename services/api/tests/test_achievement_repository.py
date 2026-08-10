import uuid
from collections.abc import AsyncGenerator
from datetime import datetime
from decimal import Decimal

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
from eop_api.repositories.achievement import AchievementRepository
from eop_api.repositories.department import DepartmentRepository
from eop_api.repositories.employment_status import EmploymentStatusRepository
from eop_api.repositories.employment_type import EmploymentTypeRepository
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.job_grade import JobGradeRepository
from eop_api.repositories.kpi import KpiRepository
from eop_api.repositories.location import LocationRepository
from eop_api.repositories.location_type import LocationTypeRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.position import PositionRepository
from eop_api.repositories.shift import ShiftRepository
from eop_api.repositories.target import TargetRepository
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
def repo(session: AsyncSession) -> AchievementRepository:
    return AchievementRepository(session)


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
async def kpi_id(session: AsyncSession) -> uuid.UUID:
    kpi = await KpiRepository(session).create(code="VCR", name="Visit Compliance Rate", unit="%")
    return kpi.id


@pytest.fixture
async def target_id(session: AsyncSession, employee_id: uuid.UUID, kpi_id: uuid.UUID) -> uuid.UUID:
    target = await TargetRepository(session).create(
        employee_id=employee_id,
        kpi_id=kpi_id,
        period_year=2026,
        period_month=8,
        goal_value=Decimal("95.5"),
    )
    return target.id


async def test_create_and_get(repo: AchievementRepository, target_id: uuid.UUID):
    achievement = await repo.create(target_id=target_id, actual_value=Decimal("90.25"))

    fetched = await repo.get(achievement.id)

    assert fetched is not None
    assert fetched.target_id == target_id
    assert fetched.actual_value == Decimal("90.25")


async def test_get_missing_returns_none(repo: AchievementRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_get_by_target_id(repo: AchievementRepository, target_id: uuid.UUID):
    achievement = await repo.create(target_id=target_id, actual_value=Decimal("10"))

    found = await repo.get_by_target_id(target_id)

    assert found is not None
    assert found.id == achievement.id
    assert await repo.get_by_target_id(uuid.uuid4()) is None


async def test_list_returns_created(repo: AchievementRepository, target_id: uuid.UUID):
    await repo.create(target_id=target_id, actual_value=Decimal("10"))

    items = await repo.list()

    assert len(items) == 1
    assert items[0].target_id == target_id


async def test_duplicate_target_rejected_at_db_level(
    repo: AchievementRepository, target_id: uuid.UUID
):
    await repo.create(target_id=target_id, actual_value=Decimal("10"))

    with pytest.raises(IntegrityError):
        await repo.create(target_id=target_id, actual_value=Decimal("99"))


async def test_update_existing(repo: AchievementRepository, target_id: uuid.UUID):
    achievement = await repo.create(target_id=target_id, actual_value=Decimal("10"))

    updated = await repo.update(achievement.id, actual_value=Decimal("42.25"))

    assert updated is not None
    assert updated.actual_value == Decimal("42.25")


async def test_delete_existing(repo: AchievementRepository, target_id: uuid.UUID):
    achievement = await repo.create(target_id=target_id, actual_value=Decimal("10"))

    deleted = await repo.delete(achievement.id)

    assert deleted is True
    assert await repo.get(achievement.id) is None


async def test_delete_missing_returns_false(repo: AchievementRepository):
    assert await repo.delete(uuid.uuid4()) is False


async def test_paginate_filters_by_target_id(repo: AchievementRepository, target_id: uuid.UUID):
    await repo.create(target_id=target_id, actual_value=Decimal("10"))

    page = await repo.paginate(filters=FilterParams(values={"target_id": target_id}))
    assert page.total == 1

    other_page = await repo.paginate(filters=FilterParams(values={"target_id": uuid.uuid4()}))
    assert other_page.total == 0


async def test_paginate_returns_total_and_page_slice(
    repo: AchievementRepository,
    session: AsyncSession,
    employee_id: uuid.UUID,
    kpi_id: uuid.UUID,
):
    for month in range(1, 6):
        target = await TargetRepository(session).create(
            employee_id=employee_id,
            kpi_id=kpi_id,
            period_year=2026,
            period_month=month,
            goal_value=Decimal("10"),
        )
        await repo.create(target_id=target.id, actual_value=Decimal("10"))

    page = await repo.paginate(offset=1, limit=2)

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_target_deletion_restricted_while_achievement_exists(
    repo: AchievementRepository, session: AsyncSession, target_id: uuid.UUID
):
    await repo.create(target_id=target_id, actual_value=Decimal("10"))

    with pytest.raises(IntegrityError):
        await TargetRepository(session).delete(target_id)
