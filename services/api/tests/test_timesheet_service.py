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
from eop_api.schemas.pagination import PaginationParams
from eop_api.schemas.timesheet import TimesheetCreate, TimesheetUpdate
from eop_api.services.timesheet import (
    EmployeeNotFoundError,
    InvalidTimesheetDateRangeError,
    InvalidTimesheetStateError,
    TimesheetService,
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
def service(session_factory: Callable[[], AsyncSession]) -> TimesheetService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return TimesheetService(uow_factory)


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


def _create(employee_id: uuid.UUID, **overrides) -> TimesheetCreate:
    values = {
        "employee_id": employee_id,
        "start_date": date(2026, 2, 10),
        "end_date": date(2026, 2, 16),
    }
    values.update(overrides)
    return TimesheetCreate(**values)


async def test_create_and_get(service: TimesheetService, employee_id: uuid.UUID):
    timesheet = await service.create(_create(employee_id))

    fetched = await service.get(timesheet.id)

    assert fetched is not None
    assert fetched.employee_id == employee_id
    assert fetched.start_date == date(2026, 2, 10)
    assert fetched.end_date == date(2026, 2, 16)
    assert fetched.status == "pending"


async def test_create_always_starts_pending(service: TimesheetService, employee_id: uuid.UUID):
    """`TimesheetCreate` has no `status` field at all, so a client-supplied
    `status` in the raw payload is dropped during validation before it ever
    reaches the service -- enforced structurally, not just by convention."""
    data = TimesheetCreate.model_validate(
        {
            "employee_id": employee_id,
            "start_date": date(2026, 2, 10),
            "end_date": date(2026, 2, 16),
            "status": "approved",
        }
    )

    timesheet = await service.create(data)

    assert timesheet.status == "pending"


async def test_create_rejects_missing_employee(service: TimesheetService):
    with pytest.raises(EmployeeNotFoundError):
        await service.create(_create(uuid.uuid4()))


async def test_create_rejects_end_date_before_start_date(
    service: TimesheetService, employee_id: uuid.UUID
):
    with pytest.raises(InvalidTimesheetDateRangeError):
        await service.create(
            _create(employee_id, start_date=date(2026, 2, 16), end_date=date(2026, 2, 10))
        )


async def test_create_allows_equal_start_and_end_date(
    service: TimesheetService, employee_id: uuid.UUID
):
    timesheet = await service.create(
        _create(employee_id, start_date=date(2026, 2, 10), end_date=date(2026, 2, 10))
    )

    assert timesheet.start_date == timesheet.end_date == date(2026, 2, 10)


async def test_get_missing_returns_none(service: TimesheetService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(service: TimesheetService, employee_id: uuid.UUID):
    await service.create(
        _create(employee_id, start_date=date(2026, 2, 10), end_date=date(2026, 2, 16))
    )
    await service.create(
        _create(employee_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 7))
    )

    items = await service.list()

    assert {date(2026, 2, 10), date(2026, 3, 1)}.issubset({item.start_date for item in items})


async def test_update_existing(service: TimesheetService, employee_id: uuid.UUID):
    timesheet = await service.create(_create(employee_id))

    updated = await service.update(timesheet.id, TimesheetUpdate(status="approved"))

    assert updated is not None
    assert updated.status == "approved"


async def test_update_missing_returns_none(service: TimesheetService):
    assert await service.update(uuid.uuid4(), TimesheetUpdate(status="approved")) is None


async def test_update_rejects_missing_employee(service: TimesheetService, employee_id: uuid.UUID):
    timesheet = await service.create(_create(employee_id))

    with pytest.raises(EmployeeNotFoundError):
        await service.update(timesheet.id, TimesheetUpdate(employee_id=uuid.uuid4()))


async def test_update_rejects_end_date_before_start_date(
    service: TimesheetService, employee_id: uuid.UUID
):
    timesheet = await service.create(_create(employee_id))

    with pytest.raises(InvalidTimesheetDateRangeError):
        await service.update(timesheet.id, TimesheetUpdate(end_date=date(2026, 2, 1)))


async def test_update_partial_payload_validated_against_effective_start_date(
    service: TimesheetService, employee_id: uuid.UUID
):
    """Only `end_date` is sent, but it must still be validated against the
    persisted `start_date` -- the effective-value merge must catch it."""
    timesheet = await service.create(
        _create(employee_id, start_date=date(2026, 2, 10), end_date=date(2026, 2, 16))
    )

    with pytest.raises(InvalidTimesheetDateRangeError):
        await service.update(timesheet.id, TimesheetUpdate(end_date=date(2026, 2, 5)))


async def test_update_rejected_when_approved(service: TimesheetService, employee_id: uuid.UUID):
    timesheet = await service.create(_create(employee_id))
    await service.update(timesheet.id, TimesheetUpdate(status="approved"))

    with pytest.raises(InvalidTimesheetStateError):
        await service.update(timesheet.id, TimesheetUpdate(start_date=date(2026, 2, 11)))


async def test_update_rejected_when_rejected(service: TimesheetService, employee_id: uuid.UUID):
    timesheet = await service.create(_create(employee_id))
    await service.update(timesheet.id, TimesheetUpdate(status="rejected"))

    with pytest.raises(InvalidTimesheetStateError):
        await service.update(timesheet.id, TimesheetUpdate(start_date=date(2026, 2, 11)))


async def test_update_status_to_approved_rejected_when_already_approved(
    service: TimesheetService, employee_id: uuid.UUID
):
    """`{"status": "approved"}` must no longer be able to reach `approved` a
    second time (or mutate at all) once a request is already decided -- the
    only path to a first `approved` transition remains this same generic
    update, from `pending`; `ApprovalService.approve_timesheet` is
    unaffected either way (it never calls `TimesheetService`)."""
    timesheet = await service.create(_create(employee_id))
    await service.update(timesheet.id, TimesheetUpdate(status="approved"))

    with pytest.raises(InvalidTimesheetStateError):
        await service.update(timesheet.id, TimesheetUpdate(status="approved"))


async def test_update_status_to_approved_rejected_when_already_rejected(
    service: TimesheetService, employee_id: uuid.UUID
):
    timesheet = await service.create(_create(employee_id))
    await service.update(timesheet.id, TimesheetUpdate(status="rejected"))

    with pytest.raises(InvalidTimesheetStateError):
        await service.update(timesheet.id, TimesheetUpdate(status="approved"))


async def test_delete_pending_succeeds(service: TimesheetService, employee_id: uuid.UUID):
    timesheet = await service.create(_create(employee_id))

    deleted = await service.delete(timesheet.id)

    assert deleted is True
    assert await service.get(timesheet.id) is None


async def test_delete_missing_returns_false(service: TimesheetService):
    assert await service.delete(uuid.uuid4()) is False


async def test_delete_approved_is_rejected(service: TimesheetService, employee_id: uuid.UUID):
    """An `approved` Timesheet -- an already-decided workflow fact -- can
    never be deleted, mirroring `update()`'s own already-established
    `pending`-only invariant. `repo.delete()` is never reached: the row
    remains exactly as it was, provable by `get()` still returning it."""
    timesheet = await service.create(_create(employee_id))
    await service.update(timesheet.id, TimesheetUpdate(status="approved"))

    with pytest.raises(InvalidTimesheetStateError):
        await service.delete(timesheet.id)

    assert await service.get(timesheet.id) is not None


async def test_delete_rejected_is_rejected(service: TimesheetService, employee_id: uuid.UUID):
    """A `rejected` Timesheet -- already a workflow-decided fact -- can
    never be deleted, for the same reason an `approved` one can't."""
    timesheet = await service.create(_create(employee_id))
    await service.update(timesheet.id, TimesheetUpdate(status="rejected"))

    with pytest.raises(InvalidTimesheetStateError):
        await service.delete(timesheet.id)

    assert await service.get(timesheet.id) is not None


async def test_list_paginated_passes_through_offset_and_limit(
    service: TimesheetService, employee_id: uuid.UUID
):
    for i in range(5):
        await service.create(
            _create(employee_id, start_date=date(2026, 2, 1 + i), end_date=date(2026, 2, 7 + i))
        )

    page = await service.list_paginated(PaginationParams(offset=1, limit=2))

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2
