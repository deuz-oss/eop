import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.core.field_attendance import FieldAttendanceEventType
from eop_api.db.base import Base
from eop_api.models.hr_employee import HrEmployee
from eop_api.models.user import User
from eop_api.repositories.department import DepartmentRepository
from eop_api.repositories.employment_status import EmploymentStatusRepository
from eop_api.repositories.employment_type import EmploymentTypeRepository
from eop_api.repositories.file import FileRepository
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.job_grade import JobGradeRepository
from eop_api.repositories.location import LocationRepository
from eop_api.repositories.location_type import LocationTypeRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.position import PositionRepository
from eop_api.repositories.shift import ShiftRepository
from eop_api.repositories.team import TeamRepository
from eop_api.schemas.field_attendance_event import (
    FieldAttendanceEventCreate,
    FieldAttendanceEventUpdate,
)
from eop_api.schemas.pagination import PaginationParams
from eop_api.schemas.search import FilterParams
from eop_api.services.employee_context import EmployeeContext, RequestContext
from eop_api.services.field_attendance_event import (
    EmployeeNotFoundError,
    FieldAttendanceAuthorizationDeniedError,
    FieldAttendanceEventService,
    SelfieFileNotFoundError,
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
                    "file_objects CASCADE"
                )
            )
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> FieldAttendanceEventService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return FieldAttendanceEventService(uow_factory)


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
async def selfie_file_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
    async with session_factory() as session:
        file_object = await FileRepository(session).create(
            filename="selfie.jpg",
            content_type="image/jpeg",
            size=1024,
            storage_key=f"selfies/{uuid.uuid4().hex}.jpg",
            bucket="eop-files",
        )
        await session.commit()
        return file_object.id


def _request_context(employee_id: uuid.UUID) -> RequestContext:
    """A `RequestContext` built entirely in memory, scoped to `employee_id`.

    Only `employee_context.employee.id` is read by
    `AttendanceAuthorizationEvaluator`/`FieldAttendanceEventService`, so the
    `User`/`HrEmployee` here need not be persisted -- mirrors
    `test_posm_audit_service.py`'s exact pattern.
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
    employee_id: uuid.UUID, selfie_file_id: uuid.UUID, **overrides
) -> FieldAttendanceEventCreate:
    values = {
        "employee_id": employee_id,
        "event_type": FieldAttendanceEventType.CHECK_IN,
        "event_time": datetime(2026, 1, 5, 9, 0, tzinfo=UTC),
        "latitude": Decimal("-6.200000"),
        "longitude": Decimal("106.816666"),
        "gps_accuracy_meters": Decimal("12.50"),
        "selfie_file_id": selfie_file_id,
    }
    values.update(overrides)
    return FieldAttendanceEventCreate(**values)


async def test_create_and_get(
    service: FieldAttendanceEventService, employee_id: uuid.UUID, selfie_file_id: uuid.UUID
):
    context = _request_context(employee_id)
    event = await service.create(_create(employee_id, selfie_file_id), context)

    fetched = await service.get(event.id, context)

    assert fetched is not None
    assert fetched.employee_id == employee_id
    assert fetched.event_type == FieldAttendanceEventType.CHECK_IN
    assert fetched.selfie_file_id == selfie_file_id


async def test_create_rejects_missing_employee(
    service: FieldAttendanceEventService, selfie_file_id: uuid.UUID
):
    missing_employee_id = uuid.uuid4()
    with pytest.raises(EmployeeNotFoundError):
        await service.create(
            _create(missing_employee_id, selfie_file_id), _request_context(missing_employee_id)
        )


async def test_create_rejects_missing_selfie_file(
    service: FieldAttendanceEventService, employee_id: uuid.UUID
):
    with pytest.raises(SelfieFileNotFoundError):
        await service.create(_create(employee_id, uuid.uuid4()), _request_context(employee_id))


async def test_create_denied_for_non_owner(
    service: FieldAttendanceEventService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    selfie_file_id: uuid.UUID,
):
    with pytest.raises(FieldAttendanceAuthorizationDeniedError):
        await service.create(
            _create(employee_id, selfie_file_id), _request_context(other_employee_id)
        )


async def test_create_allows_multiple_per_employee(
    service: FieldAttendanceEventService, employee_id: uuid.UUID, selfie_file_id: uuid.UUID
):
    context = _request_context(employee_id)
    first = await service.create(_create(employee_id, selfie_file_id), context)
    second = await service.create(
        _create(employee_id, selfie_file_id, event_type=FieldAttendanceEventType.CHECK_OUT),
        context,
    )

    assert first.id != second.id


async def test_get_missing_returns_none(
    service: FieldAttendanceEventService, employee_id: uuid.UUID
):
    assert await service.get(uuid.uuid4(), _request_context(employee_id)) is None


async def test_get_denied_for_non_owner(
    service: FieldAttendanceEventService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    selfie_file_id: uuid.UUID,
):
    owner_context = _request_context(employee_id)
    event = await service.create(_create(employee_id, selfie_file_id), owner_context)

    with pytest.raises(FieldAttendanceAuthorizationDeniedError):
        await service.get(event.id, _request_context(other_employee_id))


async def test_list_returns_only_owned(
    service: FieldAttendanceEventService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    selfie_file_id: uuid.UUID,
):
    context = _request_context(employee_id)
    other_context = _request_context(other_employee_id)
    await service.create(_create(employee_id, selfie_file_id), context)
    await service.create(_create(other_employee_id, selfie_file_id), other_context)

    items = await service.list(context)

    assert {item.employee_id for item in items} == {employee_id}


async def test_list_paginated_returns_only_owned(
    service: FieldAttendanceEventService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    selfie_file_id: uuid.UUID,
):
    context = _request_context(employee_id)
    other_context = _request_context(other_employee_id)
    await service.create(_create(employee_id, selfie_file_id), context)
    await service.create(_create(other_employee_id, selfie_file_id), other_context)

    page = await service.list_paginated(context, PaginationParams(offset=0, limit=50))

    assert page.total == 1
    assert page.items[0].employee_id == employee_id


async def test_list_paginated_ignores_client_supplied_employee_id(
    service: FieldAttendanceEventService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    selfie_file_id: uuid.UUID,
):
    """A caller cannot widen scope by passing a different `employee_id` in
    `filters` -- the service always forces its own resolved employee id."""
    context = _request_context(employee_id)
    other_context = _request_context(other_employee_id)
    await service.create(_create(employee_id, selfie_file_id), context)
    await service.create(_create(other_employee_id, selfie_file_id), other_context)

    page = await service.list_paginated(
        context,
        PaginationParams(offset=0, limit=50),
        filters=FilterParams(values={"employee_id": other_employee_id}),
    )

    assert page.total == 1
    assert page.items[0].employee_id == employee_id


async def test_update_existing(
    service: FieldAttendanceEventService, employee_id: uuid.UUID, selfie_file_id: uuid.UUID
):
    context = _request_context(employee_id)
    event = await service.create(_create(employee_id, selfie_file_id), context)

    updated = await service.update(
        event.id, FieldAttendanceEventUpdate(event_type=FieldAttendanceEventType.CHECK_OUT), context
    )

    assert updated is not None
    assert updated.event_type == FieldAttendanceEventType.CHECK_OUT


async def test_update_missing_returns_none(
    service: FieldAttendanceEventService, employee_id: uuid.UUID
):
    assert (
        await service.update(
            uuid.uuid4(),
            FieldAttendanceEventUpdate(event_type=FieldAttendanceEventType.CHECK_OUT),
            _request_context(employee_id),
        )
        is None
    )


async def test_update_denied_for_non_owner(
    service: FieldAttendanceEventService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    selfie_file_id: uuid.UUID,
):
    owner_context = _request_context(employee_id)
    event = await service.create(_create(employee_id, selfie_file_id), owner_context)

    with pytest.raises(FieldAttendanceAuthorizationDeniedError):
        await service.update(
            event.id,
            FieldAttendanceEventUpdate(event_type=FieldAttendanceEventType.CHECK_OUT),
            _request_context(other_employee_id),
        )


async def test_delete_existing(
    service: FieldAttendanceEventService, employee_id: uuid.UUID, selfie_file_id: uuid.UUID
):
    context = _request_context(employee_id)
    event = await service.create(_create(employee_id, selfie_file_id), context)

    deleted = await service.delete(event.id, context)

    assert deleted is True
    assert await service.get(event.id, context) is None


async def test_delete_missing_returns_false(
    service: FieldAttendanceEventService, employee_id: uuid.UUID
):
    assert await service.delete(uuid.uuid4(), _request_context(employee_id)) is False


async def test_delete_denied_for_non_owner(
    service: FieldAttendanceEventService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    selfie_file_id: uuid.UUID,
):
    owner_context = _request_context(employee_id)
    event = await service.create(_create(employee_id, selfie_file_id), owner_context)

    with pytest.raises(FieldAttendanceAuthorizationDeniedError):
        await service.delete(event.id, _request_context(other_employee_id))

    assert await service.get(event.id, owner_context) is not None
