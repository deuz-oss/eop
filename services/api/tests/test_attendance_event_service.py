import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.attendance import EventSource, EventType
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.models.hr_employee import HrEmployee
from eop_api.models.user import User
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
from eop_api.schemas.attendance_event import AttendanceEventCreate, AttendanceEventUpdate
from eop_api.schemas.pagination import PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.services.attendance_event import (
    AttendanceAuthorizationDeniedError,
    AttendanceEventService,
    EmployeeNotFoundError,
    ShiftNotFoundError,
)
from eop_api.services.employee_context import EmployeeContext, RequestContext
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
def service(session_factory: Callable[[], AsyncSession]) -> AttendanceEventService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return AttendanceEventService(uow_factory)


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


@pytest.fixture
async def employee_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
    return await _create_hr_employee(session_factory, suffix="a")


@pytest.fixture
async def other_employee_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
    return await _create_hr_employee(session_factory, suffix="b")


@pytest.fixture
async def shift_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
    async with session_factory() as session:
        shift = await ShiftRepository(session).create(
            code="NIGHT",
            name="Night Shift",
            start_time=datetime(2024, 1, 1, 22, 0).time(),
            end_time=datetime(2024, 1, 1, 6, 0).time(),
        )
        await session.commit()
        return shift.id


def _request_context(employee_id: uuid.UUID) -> RequestContext:
    """A `RequestContext` built entirely in memory, scoped to `employee_id`.

    Only `employee_context.employee.id` is read by
    `AttendanceAuthorizationEvaluator`/`AttendanceEventService`, so the
    `User`/`HrEmployee` here need not be persisted -- mirrors the pattern
    already used by `test_leave_request_service.py`.
    """
    user = User(
        id=uuid.uuid4(),
        email="actor@example.com",
        password_hash="hash",
        full_name="Actor",
        is_active=True,
    )
    employee = HrEmployee(
        id=employee_id,
        employee_number="ACT-1",
        first_name="Actor",
        last_name="One",
        full_name="Actor One",
        email="actor@example.com",
        organization_id=uuid.uuid4(),
        department_id=uuid.uuid4(),
        position_id=uuid.uuid4(),
        team_id=uuid.uuid4(),
        location_id=uuid.uuid4(),
        job_grade_id=uuid.uuid4(),
        employment_type_id=uuid.uuid4(),
        employment_status_id=uuid.uuid4(),
        shift_id=uuid.uuid4(),
        hire_date=date(2020, 1, 1),
        employment_status="active",
        user_id=user.id,
    )
    return RequestContext(user=user, employee_context=EmployeeContext(user=user, employee=employee))


def _create(
    employee_id: uuid.UUID, shift_id: uuid.UUID, **overrides
) -> AttendanceEventCreate:
    values = {
        "employee_id": employee_id,
        "shift_id": shift_id,
        "event_type": EventType.CLOCK_IN,
        "event_time": datetime(2026, 1, 5, 9, 0, tzinfo=UTC),
        "source": EventSource.SYSTEM,
    }
    values.update(overrides)
    return AttendanceEventCreate(**values)


async def test_create_and_get(
    service: AttendanceEventService, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    context = _request_context(employee_id)
    event = await service.create(_create(employee_id, shift_id), context)

    fetched = await service.get(event.id, context)

    assert fetched is not None
    assert fetched.employee_id == employee_id
    assert fetched.shift_id == shift_id
    assert fetched.event_type == EventType.CLOCK_IN
    assert fetched.source == EventSource.SYSTEM


async def test_create_rejects_missing_employee(
    service: AttendanceEventService, shift_id: uuid.UUID
):
    with pytest.raises(EmployeeNotFoundError):
        await service.create(
            _create(uuid.uuid4(), shift_id), _request_context(uuid.uuid4())
        )


async def test_create_rejects_missing_shift(
    service: AttendanceEventService, employee_id: uuid.UUID
):
    with pytest.raises(ShiftNotFoundError):
        await service.create(
            _create(employee_id, uuid.uuid4()), _request_context(employee_id)
        )


async def test_create_denied_for_non_owner(
    service: AttendanceEventService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    shift_id: uuid.UUID,
):
    """`employee_id` on the payload does not belong to the calling employee."""
    with pytest.raises(AttendanceAuthorizationDeniedError):
        await service.create(
            _create(employee_id, shift_id), _request_context(other_employee_id)
        )


async def test_get_missing_returns_none(
    service: AttendanceEventService, employee_id: uuid.UUID
):
    assert await service.get(uuid.uuid4(), _request_context(employee_id)) is None


async def test_get_denied_for_non_owner(
    service: AttendanceEventService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    shift_id: uuid.UUID,
):
    owner_context = _request_context(employee_id)
    event = await service.create(_create(employee_id, shift_id), owner_context)

    with pytest.raises(AttendanceAuthorizationDeniedError):
        await service.get(event.id, _request_context(other_employee_id))


async def test_list_returns_created(
    service: AttendanceEventService, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    context = _request_context(employee_id)
    await service.create(_create(employee_id, shift_id, event_type=EventType.CLOCK_IN), context)
    await service.create(
        _create(
            employee_id,
            shift_id,
            event_type=EventType.CLOCK_OUT,
            event_time=datetime(2026, 1, 5, 17, 0, tzinfo=UTC),
        ),
        context,
    )

    items = await service.list(context)

    assert {EventType.CLOCK_IN, EventType.CLOCK_OUT}.issubset({item.event_type for item in items})


async def test_list_returns_only_owned(
    service: AttendanceEventService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    shift_id: uuid.UUID,
):
    context = _request_context(employee_id)
    other_context = _request_context(other_employee_id)
    await service.create(_create(employee_id, shift_id), context)
    await service.create(_create(other_employee_id, shift_id), other_context)

    items = await service.list(context)

    assert {item.employee_id for item in items} == {employee_id}


async def test_update_existing(
    service: AttendanceEventService, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    context = _request_context(employee_id)
    event = await service.create(_create(employee_id, shift_id), context)

    updated = await service.update(event.id, AttendanceEventUpdate(remarks="Corrected"), context)

    assert updated is not None
    assert updated.remarks == "Corrected"


async def test_update_missing_returns_none(
    service: AttendanceEventService, employee_id: uuid.UUID
):
    assert (
        await service.update(
            uuid.uuid4(),
            AttendanceEventUpdate(remarks="Corrected"),
            _request_context(employee_id),
        )
        is None
    )


async def test_update_rejects_missing_employee(
    service: AttendanceEventService, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    context = _request_context(employee_id)
    event = await service.create(_create(employee_id, shift_id), context)

    with pytest.raises(EmployeeNotFoundError):
        await service.update(
            event.id, AttendanceEventUpdate(employee_id=uuid.uuid4()), context
        )


async def test_update_rejects_missing_shift(
    service: AttendanceEventService, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    context = _request_context(employee_id)
    event = await service.create(_create(employee_id, shift_id), context)

    with pytest.raises(ShiftNotFoundError):
        await service.update(event.id, AttendanceEventUpdate(shift_id=uuid.uuid4()), context)


async def test_update_denied_for_non_owner(
    service: AttendanceEventService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    shift_id: uuid.UUID,
):
    owner_context = _request_context(employee_id)
    event = await service.create(_create(employee_id, shift_id), owner_context)

    with pytest.raises(AttendanceAuthorizationDeniedError):
        await service.update(
            event.id,
            AttendanceEventUpdate(remarks="Corrected"),
            _request_context(other_employee_id),
        )


async def test_delete_existing(
    service: AttendanceEventService, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    context = _request_context(employee_id)
    event = await service.create(_create(employee_id, shift_id), context)

    deleted = await service.delete(event.id, context)

    assert deleted is True
    assert await service.get(event.id, context) is None


async def test_delete_missing_returns_false(
    service: AttendanceEventService, employee_id: uuid.UUID
):
    assert await service.delete(uuid.uuid4(), _request_context(employee_id)) is False


async def test_delete_denied_for_non_owner(
    service: AttendanceEventService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    shift_id: uuid.UUID,
):
    owner_context = _request_context(employee_id)
    event = await service.create(_create(employee_id, shift_id), owner_context)

    with pytest.raises(AttendanceAuthorizationDeniedError):
        await service.delete(event.id, _request_context(other_employee_id))

    assert await service.get(event.id, owner_context) is not None


async def test_list_paginated_passes_through_offset_and_limit(
    service: AttendanceEventService, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    context = _request_context(employee_id)
    for i in range(5):
        await service.create(
            _create(
                employee_id, shift_id, event_time=datetime(2026, 1, 5, 9, i, tzinfo=UTC)
            ),
            context,
        )

    page = await service.list_paginated(context, PaginationParams(offset=1, limit=2))

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_list_paginated_passes_through_search(
    service: AttendanceEventService, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    context = _request_context(employee_id)
    await service.create(_create(employee_id, shift_id, remarks="Late due to traffic"), context)
    await service.create(
        _create(
            employee_id,
            shift_id,
            event_time=datetime(2026, 1, 5, 17, 0, tzinfo=UTC),
            remarks="On time",
        ),
        context,
    )

    page = await service.list_paginated(
        context, PaginationParams(offset=0, limit=50), SearchParams(q="traffic")
    )

    assert page.total == 1
    assert page.items[0].remarks == "Late due to traffic"


async def test_list_paginated_returns_only_owned(
    service: AttendanceEventService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    shift_id: uuid.UUID,
):
    context = _request_context(employee_id)
    other_context = _request_context(other_employee_id)
    await service.create(_create(employee_id, shift_id), context)
    await service.create(_create(other_employee_id, shift_id), other_context)

    page = await service.list_paginated(context, PaginationParams(offset=0, limit=50))

    assert {item.employee_id for item in page.items} == {employee_id}


async def test_list_paginated_ignores_caller_supplied_employee_id_filter(
    service: AttendanceEventService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    shift_id: uuid.UUID,
):
    """A caller cannot widen scope by passing a different `employee_id` filter."""
    context = _request_context(employee_id)
    other_context = _request_context(other_employee_id)
    await service.create(_create(employee_id, shift_id), context)
    await service.create(_create(other_employee_id, shift_id), other_context)

    page = await service.list_paginated(
        context,
        PaginationParams(offset=0, limit=50),
        filters=FilterParams(values={"employee_id": other_employee_id}),
    )

    assert {item.employee_id for item in page.items} == {employee_id}
