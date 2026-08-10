import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
from eop_api.schemas.pagination import PaginationParams
from eop_api.schemas.search import FilterParams
from eop_api.services.reporting import ReportingService
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
                    "kpis CASCADE"
                )
            )
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> ReportingService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return ReportingService(uow_factory)


@pytest.fixture
async def target_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
    async with session_factory() as session:
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
        employment_type = await EmploymentTypeRepository(session).create(
            code="FT", name="Full-Time"
        )
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
        kpi = await KpiRepository(session).create(
            code="VCR", name="Visit Compliance Rate", unit="%"
        )
        target = await TargetRepository(session).create(
            employee_id=employee.id,
            kpi_id=kpi.id,
            period_year=2026,
            period_month=8,
            goal_value=Decimal("95.5"),
        )
        await session.commit()
        return target.id


async def test_list_paginated_empty(service: ReportingService):
    page = await service.list_paginated(PaginationParams(offset=0, limit=50))

    assert page.total == 0
    assert page.items == []


async def test_list_paginated_returns_line(
    service: ReportingService, session_factory: Callable[[], AsyncSession], target_id: uuid.UUID
):
    async with session_factory() as session:
        await AchievementRepository(session).create(
            target_id=target_id, actual_value=Decimal("90.25")
        )
        await session.commit()

    page = await service.list_paginated(PaginationParams(offset=0, limit=50))

    assert page.total == 1
    line = page.items[0]
    assert line.target_id == target_id
    assert line.kpi_code == "VCR"
    assert line.employee_full_name == "Ada Lovelace"
    assert line.goal_value == Decimal("95.5")
    assert line.actual_value == Decimal("90.25")


async def test_list_paginated_passes_through_filters(
    service: ReportingService, session_factory: Callable[[], AsyncSession], target_id: uuid.UUID
):
    async with session_factory() as session:
        await AchievementRepository(session).create(
            target_id=target_id, actual_value=Decimal("90.25")
        )
        await session.commit()

    page = await service.list_paginated(
        PaginationParams(offset=0, limit=50), FilterParams(values={"period_month": 9})
    )

    assert page.total == 0
