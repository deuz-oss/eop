import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import date, datetime, time

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
from eop_api.schemas.overtime_request import OvertimeRequestCreate, OvertimeRequestUpdate
from eop_api.schemas.pagination import PaginationParams
from eop_api.schemas.search import SearchParams
from eop_api.services.overtime_request import (
    EmployeeNotFoundError,
    InvalidOvertimeTimeRangeError,
    OvertimeRequestService,
)
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session_factory() -> AsyncGenerator[Callable[[], AsyncSession]]:
    """A session factory backed by the real (migration-managed) tables.

    Unlike the repository tests, the service commits internally (it owns the
    transaction boundary), so rows are truncated after each test instead of
    relying on a rolled-back transaction.
    """
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
def service(session_factory: Callable[[], AsyncSession]) -> OvertimeRequestService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return OvertimeRequestService(uow_factory)


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


def _create(employee_id: uuid.UUID, **overrides) -> OvertimeRequestCreate:
    values = {
        "employee_id": employee_id,
        "overtime_date": date(2026, 2, 10),
        "start_time": time(18, 0),
        "end_time": time(20, 0),
    }
    values.update(overrides)
    return OvertimeRequestCreate(**values)


async def test_create_and_get(service: OvertimeRequestService, employee_id: uuid.UUID):
    overtime_request = await service.create(_create(employee_id))

    fetched = await service.get(overtime_request.id)

    assert fetched is not None
    assert fetched.employee_id == employee_id
    assert fetched.overtime_date == date(2026, 2, 10)
    assert fetched.start_time == time(18, 0)
    assert fetched.end_time == time(20, 0)
    assert fetched.status == "pending"


async def test_create_rejects_missing_employee(service: OvertimeRequestService):
    with pytest.raises(EmployeeNotFoundError):
        await service.create(_create(uuid.uuid4()))


async def test_create_rejects_end_time_before_start_time(
    service: OvertimeRequestService, employee_id: uuid.UUID
):
    with pytest.raises(InvalidOvertimeTimeRangeError):
        await service.create(
            _create(employee_id, start_time=time(20, 0), end_time=time(18, 0))
        )


async def test_create_rejects_equal_start_and_end_time(
    service: OvertimeRequestService, employee_id: uuid.UUID
):
    with pytest.raises(InvalidOvertimeTimeRangeError):
        await service.create(
            _create(employee_id, start_time=time(18, 0), end_time=time(18, 0))
        )


async def test_get_missing_returns_none(service: OvertimeRequestService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(service: OvertimeRequestService, employee_id: uuid.UUID):
    await service.create(_create(employee_id, overtime_date=date(2026, 2, 10)))
    await service.create(_create(employee_id, overtime_date=date(2026, 3, 1)))

    items = await service.list()

    assert {date(2026, 2, 10), date(2026, 3, 1)}.issubset(
        {item.overtime_date for item in items}
    )


async def test_update_existing(service: OvertimeRequestService, employee_id: uuid.UUID):
    overtime_request = await service.create(_create(employee_id))

    updated = await service.update(
        overtime_request.id, OvertimeRequestUpdate(status="approved")
    )

    assert updated is not None
    assert updated.status == "approved"


async def test_update_missing_returns_none(service: OvertimeRequestService):
    assert (
        await service.update(uuid.uuid4(), OvertimeRequestUpdate(status="approved")) is None
    )


async def test_update_rejects_missing_employee(
    service: OvertimeRequestService, employee_id: uuid.UUID
):
    overtime_request = await service.create(_create(employee_id))

    with pytest.raises(EmployeeNotFoundError):
        await service.update(
            overtime_request.id, OvertimeRequestUpdate(employee_id=uuid.uuid4())
        )


async def test_update_rejects_end_time_before_start_time(
    service: OvertimeRequestService, employee_id: uuid.UUID
):
    overtime_request = await service.create(_create(employee_id))

    with pytest.raises(InvalidOvertimeTimeRangeError):
        await service.update(
            overtime_request.id, OvertimeRequestUpdate(end_time=time(17, 0))
        )


async def test_update_partial_payload_validated_against_effective_start_time(
    service: OvertimeRequestService, employee_id: uuid.UUID
):
    """Only `end_time` is sent, but it must still be validated against the
    persisted `start_time` -- the effective-value merge must catch it."""
    overtime_request = await service.create(
        _create(employee_id, start_time=time(18, 0), end_time=time(20, 0))
    )

    with pytest.raises(InvalidOvertimeTimeRangeError):
        await service.update(
            overtime_request.id, OvertimeRequestUpdate(end_time=time(17, 0))
        )


async def test_delete_existing(service: OvertimeRequestService, employee_id: uuid.UUID):
    overtime_request = await service.create(_create(employee_id))

    deleted = await service.delete(overtime_request.id)

    assert deleted is True
    assert await service.get(overtime_request.id) is None


async def test_delete_missing_returns_false(service: OvertimeRequestService):
    assert await service.delete(uuid.uuid4()) is False


async def test_list_paginated_passes_through_offset_and_limit(
    service: OvertimeRequestService, employee_id: uuid.UUID
):
    for i in range(5):
        await service.create(_create(employee_id, overtime_date=date(2026, 2, 1 + i)))

    page = await service.list_paginated(PaginationParams(offset=1, limit=2))

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_list_paginated_passes_through_search(
    service: OvertimeRequestService, employee_id: uuid.UUID
):
    await service.create(_create(employee_id, reason="Quarter-end close"))
    await service.create(
        _create(employee_id, overtime_date=date(2026, 3, 1), reason="Production incident")
    )

    page = await service.list_paginated(
        PaginationParams(offset=0, limit=50), SearchParams(q="close")
    )

    assert page.total == 1
    assert page.items[0].reason == "Quarter-end close"
