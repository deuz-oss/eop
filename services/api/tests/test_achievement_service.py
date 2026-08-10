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
from eop_api.schemas.achievement import AchievementCreate, AchievementUpdate
from eop_api.services.achievement import (
    AchievementService,
    DuplicateAchievementError,
    TargetNotFoundError,
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
                    "job_grades, employment_types, employment_statuses, shifts, "
                    "kpis CASCADE"
                )
            )
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> AchievementService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return AchievementService(uow_factory)


async def _create_hr_employee(
    session_factory: Callable[[], AsyncSession], *, suffix: str
) -> uuid.UUID:
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
            code=f"L1-{suffix}", name="Junior", level=ord(suffix[0]) - ord("a") + 1
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
        await session.commit()
        return employee.id


async def _create_kpi(session_factory: Callable[[], AsyncSession], *, suffix: str) -> uuid.UUID:
    async with session_factory() as session:
        kpi = await KpiRepository(session).create(
            code=f"VCR-{suffix}", name="Visit Compliance Rate", unit="%"
        )
        await session.commit()
        return kpi.id


async def _create_target(
    session_factory: Callable[[], AsyncSession],
    *,
    employee_id: uuid.UUID,
    kpi_id: uuid.UUID,
    period_month: int = 8,
) -> uuid.UUID:
    async with session_factory() as session:
        target = await TargetRepository(session).create(
            employee_id=employee_id,
            kpi_id=kpi_id,
            period_year=2026,
            period_month=period_month,
            goal_value=Decimal("95.5"),
        )
        await session.commit()
        return target.id


@pytest.fixture
async def employee_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
    return await _create_hr_employee(session_factory, suffix="e1")


@pytest.fixture
async def kpi_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
    return await _create_kpi(session_factory, suffix="k1")


@pytest.fixture
async def target_id(
    session_factory: Callable[[], AsyncSession], employee_id: uuid.UUID, kpi_id: uuid.UUID
) -> uuid.UUID:
    return await _create_target(session_factory, employee_id=employee_id, kpi_id=kpi_id)


def _create(target_id: uuid.UUID, **overrides) -> AchievementCreate:
    values = {"target_id": target_id, "actual_value": "90.25"}
    values.update(overrides)
    return AchievementCreate(**values)


async def test_create_and_get(service: AchievementService, target_id: uuid.UUID):
    achievement = await service.create(_create(target_id))

    fetched = await service.get(achievement.id)

    assert fetched is not None
    assert fetched.target_id == target_id
    assert fetched.actual_value == Decimal("90.25")


async def test_create_rejects_missing_target(service: AchievementService):
    with pytest.raises(TargetNotFoundError):
        await service.create(_create(uuid.uuid4()))


async def test_create_rejects_duplicate_target(service: AchievementService, target_id: uuid.UUID):
    await service.create(_create(target_id))

    with pytest.raises(DuplicateAchievementError):
        await service.create(_create(target_id))


async def test_get_missing_returns_none(service: AchievementService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(
    service: AchievementService,
    session_factory: Callable[[], AsyncSession],
    employee_id: uuid.UUID,
    kpi_id: uuid.UUID,
    target_id: uuid.UUID,
):
    other_target_id = await _create_target(
        session_factory, employee_id=employee_id, kpi_id=kpi_id, period_month=9
    )
    await service.create(_create(target_id))
    await service.create(_create(other_target_id))

    items = await service.list()

    assert {item.target_id for item in items} == {target_id, other_target_id}


async def test_update_only_actual_value(service: AchievementService, target_id: uuid.UUID):
    achievement = await service.create(_create(target_id))

    updated = await service.update(achievement.id, AchievementUpdate(actual_value="120"))

    assert updated is not None
    assert updated.actual_value == Decimal("120")
    assert updated.target_id == target_id


async def test_update_missing_returns_none(service: AchievementService):
    assert await service.update(uuid.uuid4(), AchievementUpdate(actual_value="1")) is None


def test_update_schema_carries_no_target_id_field():
    """`AchievementUpdate` has no `target_id` field at all -- identity is
    structurally immutable, not merely ignored
    (`achievement-iteration-1-scope-and-implementation-plan.md` §6)."""
    assert set(AchievementUpdate.model_fields) == {"actual_value"}


async def test_delete_existing(service: AchievementService, target_id: uuid.UUID):
    achievement = await service.create(_create(target_id))

    deleted = await service.delete(achievement.id)

    assert deleted is True
    assert await service.get(achievement.id) is None


async def test_delete_missing_returns_false(service: AchievementService):
    assert await service.delete(uuid.uuid4()) is False
