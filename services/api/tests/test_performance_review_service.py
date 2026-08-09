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
from eop_api.repositories.team import TeamRepository
from eop_api.schemas.performance_review import PerformanceReviewCreate, PerformanceReviewUpdate
from eop_api.services.performance_review import (
    EmployeeNotFoundError,
    InvalidPerformanceReviewPeriodError,
    PerformanceReviewService,
)
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
                    "job_grades, employment_types, employment_statuses, shifts CASCADE"
                )
            )
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> PerformanceReviewService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return PerformanceReviewService(uow_factory)


@pytest.fixture
async def employee_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
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
        await session.commit()
        return employee.id


def _create(employee_id: uuid.UUID, **overrides) -> PerformanceReviewCreate:
    values = {
        "employee_id": employee_id,
        "review_period_start": date(2026, 1, 1),
        "review_period_end": date(2026, 6, 30),
    }
    values.update(overrides)
    return PerformanceReviewCreate(**values)


async def test_create_and_get(service: PerformanceReviewService, employee_id: uuid.UUID):
    review = await service.create(_create(employee_id))

    fetched = await service.get(review.id)

    assert fetched is not None
    assert fetched.employee_id == employee_id


async def test_create_rejects_missing_employee(service: PerformanceReviewService):
    with pytest.raises(EmployeeNotFoundError):
        await service.create(_create(uuid.uuid4()))


async def test_create_rejects_invalid_period(
    service: PerformanceReviewService, employee_id: uuid.UUID
):
    with pytest.raises(InvalidPerformanceReviewPeriodError):
        await service.create(
            _create(
                employee_id,
                review_period_start=date(2026, 6, 30),
                review_period_end=date(2026, 1, 1),
            )
        )


async def test_get_missing_returns_none(service: PerformanceReviewService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(service: PerformanceReviewService, employee_id: uuid.UUID):
    first = await service.create(_create(employee_id))
    second = await service.create(
        _create(
            employee_id, review_period_start=date(2026, 7, 1), review_period_end=date(2026, 12, 31)
        )
    )

    items = await service.list()

    assert {first.id, second.id}.issubset({item.id for item in items})


async def test_update_existing(service: PerformanceReviewService, employee_id: uuid.UUID):
    review = await service.create(_create(employee_id))

    updated = await service.update(review.id, PerformanceReviewUpdate(notes="Updated"))

    assert updated is not None
    assert updated.notes == "Updated"


async def test_update_missing_returns_none(service: PerformanceReviewService):
    assert await service.update(uuid.uuid4(), PerformanceReviewUpdate(notes="x")) is None


async def test_update_rejects_missing_employee(
    service: PerformanceReviewService, employee_id: uuid.UUID
):
    review = await service.create(_create(employee_id))

    with pytest.raises(EmployeeNotFoundError):
        await service.update(review.id, PerformanceReviewUpdate(employee_id=uuid.uuid4()))


async def test_update_rejects_invalid_period(
    service: PerformanceReviewService, employee_id: uuid.UUID
):
    review = await service.create(_create(employee_id))

    with pytest.raises(InvalidPerformanceReviewPeriodError):
        await service.update(review.id, PerformanceReviewUpdate(review_period_end=date(2025, 1, 1)))


async def test_delete_existing(service: PerformanceReviewService, employee_id: uuid.UUID):
    review = await service.create(_create(employee_id))

    deleted = await service.delete(review.id)

    assert deleted is True
    assert await service.get(review.id) is None


async def test_delete_missing_returns_false(service: PerformanceReviewService):
    assert await service.delete(uuid.uuid4()) is False
