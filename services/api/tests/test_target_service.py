import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import datetime

import pytest
from pydantic import ValidationError
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
from eop_api.repositories.team import TeamRepository
from eop_api.schemas.target import TargetCreate, TargetUpdate
from eop_api.services.target import (
    DuplicateTargetError,
    EmployeeNotFoundError,
    KpiNotFoundError,
    TargetService,
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
def service(session_factory: Callable[[], AsyncSession]) -> TargetService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return TargetService(uow_factory)


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


@pytest.fixture
async def employee_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
    return await _create_hr_employee(session_factory, suffix="e1")


@pytest.fixture
async def kpi_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
    return await _create_kpi(session_factory, suffix="k1")


def _create(kpi_id: uuid.UUID, employee_id: uuid.UUID, **overrides) -> TargetCreate:
    values = {
        "kpi_id": kpi_id,
        "employee_id": employee_id,
        "period_year": 2026,
        "period_month": 8,
        "goal_value": "95.5",
    }
    values.update(overrides)
    return TargetCreate(**values)


async def test_create_and_get(service: TargetService, kpi_id: uuid.UUID, employee_id: uuid.UUID):
    target = await service.create(_create(kpi_id, employee_id))

    fetched = await service.get(target.id)

    assert fetched is not None
    assert fetched.kpi_id == kpi_id
    assert fetched.employee_id == employee_id
    assert fetched.period_year == 2026
    assert fetched.period_month == 8
    assert fetched.goal_value == 95.5


async def test_create_rejects_missing_kpi(service: TargetService, employee_id: uuid.UUID):
    with pytest.raises(KpiNotFoundError):
        await service.create(_create(uuid.uuid4(), employee_id))


async def test_create_rejects_missing_employee(service: TargetService, kpi_id: uuid.UUID):
    with pytest.raises(EmployeeNotFoundError):
        await service.create(_create(kpi_id, uuid.uuid4()))


async def test_create_rejects_duplicate_identity(
    service: TargetService, kpi_id: uuid.UUID, employee_id: uuid.UUID
):
    await service.create(_create(kpi_id, employee_id))

    with pytest.raises(DuplicateTargetError):
        await service.create(_create(kpi_id, employee_id))


async def test_create_allows_same_employee_kpi_different_month(
    service: TargetService, kpi_id: uuid.UUID, employee_id: uuid.UUID
):
    await service.create(_create(kpi_id, employee_id, period_month=8))
    other = await service.create(_create(kpi_id, employee_id, period_month=9))

    assert other.period_month == 9


def test_create_rejects_month_above_range():
    with pytest.raises(ValidationError):
        TargetCreate(
            kpi_id=uuid.uuid4(),
            employee_id=uuid.uuid4(),
            period_year=2026,
            period_month=13,
            goal_value="1",
        )


def test_create_rejects_month_below_range():
    with pytest.raises(ValidationError):
        TargetCreate(
            kpi_id=uuid.uuid4(),
            employee_id=uuid.uuid4(),
            period_year=2026,
            period_month=0,
            goal_value="1",
        )


async def test_get_missing_returns_none(service: TargetService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(
    service: TargetService, kpi_id: uuid.UUID, employee_id: uuid.UUID
):
    await service.create(_create(kpi_id, employee_id, period_month=8))
    await service.create(_create(kpi_id, employee_id, period_month=9))

    items = await service.list()

    assert {item.period_month for item in items}.issuperset({8, 9})


async def test_update_only_goal_value(
    service: TargetService, kpi_id: uuid.UUID, employee_id: uuid.UUID
):
    target = await service.create(_create(kpi_id, employee_id))

    updated = await service.update(target.id, TargetUpdate(goal_value="120"))

    assert updated is not None
    assert updated.goal_value == 120
    assert updated.kpi_id == kpi_id
    assert updated.employee_id == employee_id
    assert updated.period_year == 2026
    assert updated.period_month == 8


async def test_update_missing_returns_none(service: TargetService):
    assert await service.update(uuid.uuid4(), TargetUpdate(goal_value="1")) is None


async def test_update_schema_carries_no_identity_fields():
    """`TargetUpdate` has no `kpi_id`/`employee_id`/`period_year`/
    `period_month` field at all -- identity is structurally immutable, not
    merely ignored (`target-iteration-1-scope-and-implementation-plan.md`
    §14)."""
    assert set(TargetUpdate.model_fields) == {"goal_value"}


async def test_delete_existing(service: TargetService, kpi_id: uuid.UUID, employee_id: uuid.UUID):
    target = await service.create(_create(kpi_id, employee_id))

    deleted = await service.delete(target.id)

    assert deleted is True
    assert await service.get(target.id) is None


async def test_delete_missing_returns_false(service: TargetService):
    assert await service.delete(uuid.uuid4()) is False
