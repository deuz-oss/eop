import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import UTC, date, datetime, time

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.attendance import EventSource, EventType
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
from eop_api.schemas.attendance_event import AttendanceEventCreate
from eop_api.schemas.holiday import HolidayCreate
from eop_api.schemas.leave_request import LeaveRequestCreate, LeaveRequestUpdate
from eop_api.services.attendance_event import AttendanceEventService
from eop_api.services.holiday import HolidayService
from eop_api.services.leave_request import LeaveRequestService
from eop_api.services.reconciliation import EmployeeNotFoundError, ReconciliationService
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio

TARGET_DATE = date(2026, 3, 2)


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
                    "job_grades, employment_types, employment_statuses, shifts, users, "
                    "holidays CASCADE"
                )
            )
        await engine.dispose()


@pytest.fixture
def uow_factory(
    session_factory: Callable[[], AsyncSession],
) -> Callable[[], SQLAlchemyUnitOfWork]:
    return lambda: SQLAlchemyUnitOfWork(session_factory)  # noqa: E731


@pytest.fixture
def service(uow_factory: Callable[[], SQLAlchemyUnitOfWork]) -> ReconciliationService:
    return ReconciliationService(uow_factory)


@pytest.fixture
def leave_request_service(
    uow_factory: Callable[[], SQLAlchemyUnitOfWork],
) -> LeaveRequestService:
    return LeaveRequestService(uow_factory)


@pytest.fixture
def attendance_event_service(
    uow_factory: Callable[[], SQLAlchemyUnitOfWork],
) -> AttendanceEventService:
    return AttendanceEventService(uow_factory)


@pytest.fixture
def holiday_service(uow_factory: Callable[[], SQLAlchemyUnitOfWork]) -> HolidayService:
    return HolidayService(uow_factory)


@pytest.fixture
async def employee(
    session_factory: Callable[[], AsyncSession],
) -> tuple[uuid.UUID, uuid.UUID]:
    """Creates one HrEmployee (and its Shift). Returns `(employee_id, shift_id)`."""
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
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        hr_employee = await HrEmployeeRepository(session).create(
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
            hire_date=date(2024, 1, 15),
            employment_status="active",
        )
        await session.commit()
        return hr_employee.id, shift.id


@pytest.fixture
def employee_id(employee: tuple[uuid.UUID, uuid.UUID]) -> uuid.UUID:
    return employee[0]


@pytest.fixture
def shift_id(employee: tuple[uuid.UUID, uuid.UUID]) -> uuid.UUID:
    return employee[1]


async def _approved_leave_request(
    leave_request_service: LeaveRequestService,
    employee_id: uuid.UUID,
    *,
    start_date: date = date(2026, 3, 1),
    end_date: date = date(2026, 3, 3),
) -> uuid.UUID:
    leave_request = await leave_request_service.create(
        LeaveRequestCreate(employee_id=employee_id, start_date=start_date, end_date=end_date)
    )
    await leave_request_service.update(leave_request.id, LeaveRequestUpdate(status="approved"))
    return leave_request.id


async def _attendance_event(
    attendance_event_service: AttendanceEventService,
    employee_id: uuid.UUID,
    shift_id: uuid.UUID,
    *,
    event_time: datetime = datetime(2026, 3, 2, 9, 0, tzinfo=UTC),
) -> uuid.UUID:
    event = await attendance_event_service.create(
        AttendanceEventCreate(
            employee_id=employee_id,
            shift_id=shift_id,
            event_type=EventType.CLOCK_IN,
            event_time=event_time,
            source=EventSource.SYSTEM,
        )
    )
    return event.id


# --- Employee existence ------------------------------------------------------


async def test_reconcile_missing_employee_raises(service: ReconciliationService):
    with pytest.raises(EmployeeNotFoundError):
        await service.reconcile(uuid.uuid4(), TARGET_DATE)


# --- Individual rules ---------------------------------------------------------


async def test_reconcile_absent_when_no_facts(
    service: ReconciliationService, employee_id: uuid.UUID
):
    result = await service.reconcile(employee_id, TARGET_DATE)

    assert result.employee_id == employee_id
    assert result.date == TARGET_DATE
    assert result.status == "absent"


async def test_reconcile_present_when_attendance_event_exists(
    service: ReconciliationService,
    attendance_event_service: AttendanceEventService,
    employee_id: uuid.UUID,
    shift_id: uuid.UUID,
):
    await _attendance_event(attendance_event_service, employee_id, shift_id)

    result = await service.reconcile(employee_id, TARGET_DATE)

    assert result.status == "present"


async def test_reconcile_leave_when_approved_leave_request_covers_date(
    service: ReconciliationService,
    leave_request_service: LeaveRequestService,
    employee_id: uuid.UUID,
):
    await _approved_leave_request(leave_request_service, employee_id)

    result = await service.reconcile(employee_id, TARGET_DATE)

    assert result.status == "leave"


async def test_reconcile_ignores_pending_leave_request(
    service: ReconciliationService,
    leave_request_service: LeaveRequestService,
    employee_id: uuid.UUID,
):
    await leave_request_service.create(
        LeaveRequestCreate(
            employee_id=employee_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 3)
        )
    )

    result = await service.reconcile(employee_id, TARGET_DATE)

    assert result.status == "absent"


async def test_reconcile_holiday_when_date_is_holiday(
    service: ReconciliationService,
    holiday_service: HolidayService,
    employee_id: uuid.UUID,
):
    await holiday_service.create(
        HolidayCreate(code="HOL-1", name="Founders Day", holiday_date=TARGET_DATE)
    )

    result = await service.reconcile(employee_id, TARGET_DATE)

    assert result.status == "holiday"


# --- Precedence order ---------------------------------------------------------


async def test_reconcile_precedence_holiday_beats_leave_and_attendance(
    service: ReconciliationService,
    holiday_service: HolidayService,
    leave_request_service: LeaveRequestService,
    attendance_event_service: AttendanceEventService,
    employee_id: uuid.UUID,
    shift_id: uuid.UUID,
):
    await holiday_service.create(
        HolidayCreate(code="HOL-1", name="Founders Day", holiday_date=TARGET_DATE)
    )
    await _approved_leave_request(leave_request_service, employee_id)
    await _attendance_event(attendance_event_service, employee_id, shift_id)

    result = await service.reconcile(employee_id, TARGET_DATE)

    assert result.status == "holiday"


async def test_reconcile_precedence_leave_beats_attendance(
    service: ReconciliationService,
    leave_request_service: LeaveRequestService,
    attendance_event_service: AttendanceEventService,
    employee_id: uuid.UUID,
    shift_id: uuid.UUID,
):
    await _approved_leave_request(leave_request_service, employee_id)
    await _attendance_event(attendance_event_service, employee_id, shift_id)

    result = await service.reconcile(employee_id, TARGET_DATE)

    assert result.status == "leave"
