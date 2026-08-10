import uuid
from collections.abc import AsyncGenerator
from datetime import datetime
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
from eop_api.repositories.reporting import ReportingRepository
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
def repo(session: AsyncSession) -> ReportingRepository:
    return ReportingRepository(session)


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


async def test_paginate_empty(repo: ReportingRepository):
    page = await repo.paginate()

    assert page.total == 0
    assert page.items == []


async def test_paginate_returns_joined_row(
    repo: ReportingRepository,
    session: AsyncSession,
    employee_id: uuid.UUID,
    kpi_id: uuid.UUID,
    target_id: uuid.UUID,
):
    achievement = await AchievementRepository(session).create(
        target_id=target_id, actual_value=Decimal("90.25")
    )

    page = await repo.paginate()

    assert page.total == 1
    row = page.items[0]
    assert row.achievement_id == achievement.id
    assert row.target_id == target_id
    assert row.kpi_id == kpi_id
    assert row.kpi_code == "VCR"
    assert row.kpi_name == "Visit Compliance Rate"
    assert row.employee_id == employee_id
    assert row.employee_number == "EMP-1"
    assert row.employee_full_name == "Ada Lovelace"
    assert row.period_year == 2026
    assert row.period_month == 8
    assert row.goal_value == Decimal("95.5")
    assert row.actual_value == Decimal("90.25")


async def test_target_without_achievement_not_returned(
    repo: ReportingRepository, target_id: uuid.UUID
):
    page = await repo.paginate()

    assert page.total == 0


async def test_paginate_filters_by_employee_id(
    repo: ReportingRepository,
    session: AsyncSession,
    employee_id: uuid.UUID,
    target_id: uuid.UUID,
):
    await AchievementRepository(session).create(target_id=target_id, actual_value=Decimal("10"))

    page = await repo.paginate(filters=FilterParams(values={"employee_id": employee_id}))
    assert page.total == 1

    other_page = await repo.paginate(filters=FilterParams(values={"employee_id": uuid.uuid4()}))
    assert other_page.total == 0


async def test_paginate_filters_by_kpi_id(
    repo: ReportingRepository, session: AsyncSession, kpi_id: uuid.UUID, target_id: uuid.UUID
):
    await AchievementRepository(session).create(target_id=target_id, actual_value=Decimal("10"))

    page = await repo.paginate(filters=FilterParams(values={"kpi_id": kpi_id}))
    assert page.total == 1

    other_page = await repo.paginate(filters=FilterParams(values={"kpi_id": uuid.uuid4()}))
    assert other_page.total == 0


async def test_paginate_filters_by_period(
    repo: ReportingRepository, session: AsyncSession, target_id: uuid.UUID
):
    await AchievementRepository(session).create(target_id=target_id, actual_value=Decimal("10"))

    page = await repo.paginate(
        filters=FilterParams(values={"period_year": 2026, "period_month": 8})
    )
    assert page.total == 1

    other_page = await repo.paginate(
        filters=FilterParams(values={"period_year": 2026, "period_month": 9})
    )
    assert other_page.total == 0


async def test_paginate_returns_total_and_page_slice(
    repo: ReportingRepository, session: AsyncSession, employee_id: uuid.UUID, kpi_id: uuid.UUID
):
    for month in range(1, 6):
        target = await TargetRepository(session).create(
            employee_id=employee_id,
            kpi_id=kpi_id,
            period_year=2026,
            period_month=month,
            goal_value=Decimal("10"),
        )
        await AchievementRepository(session).create(target_id=target.id, actual_value=Decimal("10"))

    page = await repo.paginate(offset=1, limit=2)

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2
