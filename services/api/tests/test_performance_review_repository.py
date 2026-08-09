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
from eop_api.repositories.performance_review import PerformanceReviewRepository
from eop_api.repositories.position import PositionRepository
from eop_api.repositories.shift import ShiftRepository
from eop_api.repositories.team import TeamRepository

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
def repo(session: AsyncSession) -> PerformanceReviewRepository:
    return PerformanceReviewRepository(session)


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


async def test_create_and_get(repo: PerformanceReviewRepository, employee_id: uuid.UUID):
    review = await repo.create(
        employee_id=employee_id,
        review_period_start=date(2026, 1, 1),
        review_period_end=date(2026, 6, 30),
        notes="Solid first half",
    )

    fetched = await repo.get(review.id)

    assert fetched is not None
    assert fetched.employee_id == employee_id
    assert fetched.review_period_start == date(2026, 1, 1)
    assert fetched.review_period_end == date(2026, 6, 30)
    assert fetched.notes == "Solid first half"


async def test_get_missing_returns_none(repo: PerformanceReviewRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_multiple_reviews_per_employee_allowed(
    repo: PerformanceReviewRepository, employee_id: uuid.UUID
):
    first = await repo.create(
        employee_id=employee_id,
        review_period_start=date(2026, 1, 1),
        review_period_end=date(2026, 6, 30),
    )
    second = await repo.create(
        employee_id=employee_id,
        review_period_start=date(2026, 7, 1),
        review_period_end=date(2026, 12, 31),
    )

    assert first.id != second.id


async def test_update_existing(repo: PerformanceReviewRepository, employee_id: uuid.UUID):
    review = await repo.create(
        employee_id=employee_id,
        review_period_start=date(2026, 1, 1),
        review_period_end=date(2026, 6, 30),
    )

    updated = await repo.update(review.id, notes="Updated")

    assert updated is not None
    assert updated.notes == "Updated"


async def test_delete_existing(repo: PerformanceReviewRepository, employee_id: uuid.UUID):
    review = await repo.create(
        employee_id=employee_id,
        review_period_start=date(2026, 1, 1),
        review_period_end=date(2026, 6, 30),
    )

    deleted = await repo.delete(review.id)

    assert deleted is True
    assert await repo.get(review.id) is None


async def test_paginate_filters_by_employee_id(
    repo: PerformanceReviewRepository, employee_id: uuid.UUID
):
    from eop_api.schemas.search import FilterParams

    await repo.create(
        employee_id=employee_id,
        review_period_start=date(2026, 1, 1),
        review_period_end=date(2026, 6, 30),
    )

    page = await repo.paginate(filters=FilterParams(values={"employee_id": employee_id}))

    assert page.total == 1

    page_other = await repo.paginate(filters=FilterParams(values={"employee_id": uuid.uuid4()}))
    assert page_other.total == 0
