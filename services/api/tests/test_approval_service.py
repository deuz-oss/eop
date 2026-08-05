import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import date, time

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.core.security import hash_password
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
from eop_api.repositories.user import UserRepository
from eop_api.schemas.leave_request import LeaveRequestCreate
from eop_api.schemas.overtime_request import OvertimeRequestCreate
from eop_api.schemas.timesheet import TimesheetCreate
from eop_api.services.approval import (
    ApprovalAuthorizationDeniedError,
    ApprovalService,
    InvalidApprovalStateError,
)
from eop_api.services.employee_context import EmployeeContext, RequestContext
from eop_api.services.leave_request import LeaveRequestService
from eop_api.services.overtime_request import OvertimeRequestService
from eop_api.services.timesheet import TimesheetService
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
                    "job_grades, employment_types, employment_statuses, shifts, users CASCADE"
                )
            )
        await engine.dispose()


@pytest.fixture
def uow_factory(
    session_factory: Callable[[], AsyncSession],
) -> Callable[[], SQLAlchemyUnitOfWork]:
    return lambda: SQLAlchemyUnitOfWork(session_factory)  # noqa: E731


@pytest.fixture
def service(uow_factory: Callable[[], SQLAlchemyUnitOfWork]) -> ApprovalService:
    return ApprovalService(uow_factory)


@pytest.fixture
def leave_request_service(
    uow_factory: Callable[[], SQLAlchemyUnitOfWork],
) -> LeaveRequestService:
    return LeaveRequestService(uow_factory)


@pytest.fixture
def overtime_request_service(
    uow_factory: Callable[[], SQLAlchemyUnitOfWork],
) -> OvertimeRequestService:
    return OvertimeRequestService(uow_factory)


@pytest.fixture
def timesheet_service(uow_factory: Callable[[], SQLAlchemyUnitOfWork]) -> TimesheetService:
    return TimesheetService(uow_factory)


@pytest.fixture
async def _scaffolding(session_factory: Callable[[], AsyncSession]) -> dict[str, uuid.UUID]:
    """HR master data shared by every `HrEmployee` created in this file.

    Factored out so the manager/requester/non-manager employees created for
    Approval Authorization (`ADR-008`) belong to the same organization
    instead of each fixture re-creating its own.
    """
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
        await session.commit()
        return {
            "organization_id": organization.id,
            "department_id": department.id,
            "position_id": position.id,
            "team_id": team.id,
            "location_id": location.id,
            "job_grade_id": job_grade.id,
            "employment_type_id": employment_type.id,
            "employment_status_id": employment_status.id,
            "shift_id": shift.id,
        }


@pytest.fixture
async def manager_user_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
    async with session_factory() as session:
        user = await UserRepository(session).create(
            email="manager@example.com",
            password_hash=hash_password("manager-pass"),
            full_name="Manager User",
            is_active=True,
        )
        await session.commit()
        return user.id


@pytest.fixture
async def other_user_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
    async with session_factory() as session:
        user = await UserRepository(session).create(
            email="other@example.com",
            password_hash=hash_password("other-pass"),
            full_name="Other User",
            is_active=True,
        )
        await session.commit()
        return user.id


@pytest.fixture
async def manager_employee_id(
    session_factory: Callable[[], AsyncSession],
    _scaffolding: dict[str, uuid.UUID],
    manager_user_id: uuid.UUID,
) -> uuid.UUID:
    """The requester's direct manager (`HrEmployee.manager_id` target), linked
    to `manager_user_id` so it resolves to an `EmployeeContext` on approval.
    """
    async with session_factory() as session:
        manager = await HrEmployeeRepository(session).create(
            employee_number="MGR-1",
            first_name="Grace",
            last_name="Hopper",
            full_name="Grace Hopper",
            email="grace@example.com",
            user_id=manager_user_id,
            hire_date=date(2020, 1, 1),
            employment_status="active",
            **_scaffolding,
        )
        await session.commit()
        return manager.id


@pytest.fixture
async def other_employee_id(
    session_factory: Callable[[], AsyncSession],
    _scaffolding: dict[str, uuid.UUID],
    other_user_id: uuid.UUID,
) -> uuid.UUID:
    """An `HrEmployee` linked to `other_user_id`, deliberately *not* set as
    anyone's manager -- used as the non-manager (denied) approver.
    """
    async with session_factory() as session:
        other = await HrEmployeeRepository(session).create(
            employee_number="OTH-1",
            first_name="Bob",
            last_name="Smith",
            full_name="Bob Smith",
            email="bob@example.com",
            user_id=other_user_id,
            hire_date=date(2020, 1, 1),
            employment_status="active",
            **_scaffolding,
        )
        await session.commit()
        return other.id


@pytest.fixture
async def employee_id(
    session_factory: Callable[[], AsyncSession],
    _scaffolding: dict[str, uuid.UUID],
    manager_employee_id: uuid.UUID,
) -> uuid.UUID:
    """The requester, whose direct manager is `manager_employee_id`."""
    async with session_factory() as session:
        employee = await HrEmployeeRepository(session).create(
            employee_number="EMP-1",
            first_name="Ada",
            last_name="Lovelace",
            full_name="Ada Lovelace",
            email="ada@example.com",
            manager_id=manager_employee_id,
            hire_date=date(2024, 1, 15),
            employment_status="active",
            **_scaffolding,
        )
        await session.commit()
        return employee.id


async def _request_context_for(
    session_factory: Callable[[], AsyncSession], *, user_id: uuid.UUID, employee_id: uuid.UUID
) -> RequestContext:
    async with session_factory() as session:
        user = await UserRepository(session).get(user_id)
        employee = await HrEmployeeRepository(session).get(employee_id)
        assert user is not None
        assert employee is not None
        session.expunge(user)
        session.expunge(employee)
    return RequestContext(user=user, employee_context=EmployeeContext(user=user, employee=employee))


@pytest.fixture
async def manager_request_context(
    session_factory: Callable[[], AsyncSession],
    manager_user_id: uuid.UUID,
    manager_employee_id: uuid.UUID,
) -> RequestContext:
    """The requester's direct manager, resolved as an authenticated caller --
    the only actor the Approval Authorization Policy (`ADR-008`) allows.
    """
    return await _request_context_for(
        session_factory, user_id=manager_user_id, employee_id=manager_employee_id
    )


@pytest.fixture
async def other_request_context(
    session_factory: Callable[[], AsyncSession],
    other_user_id: uuid.UUID,
    other_employee_id: uuid.UUID,
) -> RequestContext:
    """An authenticated caller who is not the requester's manager -- must be
    denied by the Approval Authorization Policy.
    """
    return await _request_context_for(
        session_factory, user_id=other_user_id, employee_id=other_employee_id
    )


def _owner_request_context(employee_id: uuid.UUID) -> RequestContext:
    """An in-memory `RequestContext` scoped to `employee_id`, sufficient for
    `LeaveRequestService`'s Owner Only authorization check (`LeaveAuthorizationEvaluator`
    only reads `context.employee_context.employee.id`) -- mirrors
    `test_leave_request_service.py`'s own `_request_context` helper. The
    requester `HrEmployee` created by the `employee_id` fixture above has no
    linked `user_id` of its own (only the manager/other actors need a real,
    resolvable identity for Approval Authorization), so this in-memory
    context -- not `_request_context_for` -- is what `LeaveRequestService`
    calls need to create/read the requester's own `LeaveRequest`.
    """
    user = User(
        id=uuid.uuid4(),
        email="requester@example.com",
        password_hash="hash",
        full_name="Requester",
        is_active=True,
    )
    employee = HrEmployee(
        id=employee_id,
        employee_number="REQ-1",
        first_name="Requester",
        last_name="One",
        full_name="Requester One",
        email="requester@example.com",
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


async def _leave_request_id(
    leave_request_service: LeaveRequestService, employee_id: uuid.UUID
) -> uuid.UUID:
    leave_request = await leave_request_service.create(
        LeaveRequestCreate(
            employee_id=employee_id, start_date=date(2026, 2, 10), end_date=date(2026, 2, 12)
        ),
        _owner_request_context(employee_id),
    )
    return leave_request.id


async def _overtime_request_id(
    overtime_request_service: OvertimeRequestService, employee_id: uuid.UUID
) -> uuid.UUID:
    overtime_request = await overtime_request_service.create(
        OvertimeRequestCreate(
            employee_id=employee_id,
            overtime_date=date(2026, 2, 10),
            start_time=time(18, 0),
            end_time=time(20, 0),
        )
    )
    return overtime_request.id


async def _timesheet_id(
    timesheet_service: TimesheetService, employee_id: uuid.UUID
) -> uuid.UUID:
    timesheet = await timesheet_service.create(
        TimesheetCreate(
            employee_id=employee_id, start_date=date(2026, 2, 10), end_date=date(2026, 2, 16)
        )
    )
    return timesheet.id


# --- LeaveRequest -------------------------------------------------------


async def test_approve_leave_request(
    service: ApprovalService,
    leave_request_service: LeaveRequestService,
    employee_id: uuid.UUID,
    manager_user_id: uuid.UUID,
    manager_request_context: RequestContext,
):
    leave_request_id = await _leave_request_id(leave_request_service, employee_id)

    approved = await service.approve_leave_request(leave_request_id, manager_request_context)

    assert approved is not None
    assert approved.status == "approved"
    assert approved.approved_by == manager_user_id
    assert approved.approved_at is not None
    assert approved.rejection_reason is None


async def test_reject_leave_request(
    service: ApprovalService,
    leave_request_service: LeaveRequestService,
    employee_id: uuid.UUID,
    manager_user_id: uuid.UUID,
    manager_request_context: RequestContext,
):
    leave_request_id = await _leave_request_id(leave_request_service, employee_id)

    rejected = await service.reject_leave_request(
        leave_request_id, manager_request_context, "Insufficient coverage"
    )

    assert rejected is not None
    assert rejected.status == "rejected"
    assert rejected.approved_by == manager_user_id
    assert rejected.approved_at is not None
    assert rejected.rejection_reason == "Insufficient coverage"


async def test_approve_leave_request_missing_returns_none(
    service: ApprovalService, manager_request_context: RequestContext
):
    assert await service.approve_leave_request(uuid.uuid4(), manager_request_context) is None


async def test_reject_leave_request_missing_returns_none(
    service: ApprovalService, manager_request_context: RequestContext
):
    result = await service.reject_leave_request(uuid.uuid4(), manager_request_context, "No")
    assert result is None


async def test_approve_leave_request_rejects_non_pending(
    service: ApprovalService,
    leave_request_service: LeaveRequestService,
    employee_id: uuid.UUID,
    manager_request_context: RequestContext,
):
    leave_request_id = await _leave_request_id(leave_request_service, employee_id)
    await service.approve_leave_request(leave_request_id, manager_request_context)

    with pytest.raises(InvalidApprovalStateError):
        await service.approve_leave_request(leave_request_id, manager_request_context)


async def test_reject_leave_request_rejects_non_pending(
    service: ApprovalService,
    leave_request_service: LeaveRequestService,
    employee_id: uuid.UUID,
    manager_request_context: RequestContext,
):
    leave_request_id = await _leave_request_id(leave_request_service, employee_id)
    await service.reject_leave_request(leave_request_id, manager_request_context, "No")

    with pytest.raises(InvalidApprovalStateError):
        await service.reject_leave_request(leave_request_id, manager_request_context, "No")


async def test_approve_leave_request_denied_for_non_manager(
    service: ApprovalService,
    leave_request_service: LeaveRequestService,
    employee_id: uuid.UUID,
    other_request_context: RequestContext,
):
    leave_request_id = await _leave_request_id(leave_request_service, employee_id)

    with pytest.raises(ApprovalAuthorizationDeniedError):
        await service.approve_leave_request(leave_request_id, other_request_context)

    unchanged = await leave_request_service.get(
        leave_request_id, _owner_request_context(employee_id)
    )
    assert unchanged is not None
    assert unchanged.status == "pending"


async def test_reject_leave_request_denied_for_non_manager(
    service: ApprovalService,
    leave_request_service: LeaveRequestService,
    employee_id: uuid.UUID,
    other_request_context: RequestContext,
):
    leave_request_id = await _leave_request_id(leave_request_service, employee_id)

    with pytest.raises(ApprovalAuthorizationDeniedError):
        await service.reject_leave_request(leave_request_id, other_request_context, "No")

    unchanged = await leave_request_service.get(
        leave_request_id, _owner_request_context(employee_id)
    )
    assert unchanged is not None
    assert unchanged.status == "pending"


# --- OvertimeRequest ------------------------------------------------------


async def test_approve_overtime_request(
    service: ApprovalService,
    overtime_request_service: OvertimeRequestService,
    employee_id: uuid.UUID,
    manager_user_id: uuid.UUID,
    manager_request_context: RequestContext,
):
    overtime_request_id = await _overtime_request_id(overtime_request_service, employee_id)

    approved = await service.approve_overtime_request(overtime_request_id, manager_request_context)

    assert approved is not None
    assert approved.status == "approved"
    assert approved.approved_by == manager_user_id
    assert approved.approved_at is not None
    assert approved.rejection_reason is None


async def test_reject_overtime_request(
    service: ApprovalService,
    overtime_request_service: OvertimeRequestService,
    employee_id: uuid.UUID,
    manager_user_id: uuid.UUID,
    manager_request_context: RequestContext,
):
    overtime_request_id = await _overtime_request_id(overtime_request_service, employee_id)

    rejected = await service.reject_overtime_request(
        overtime_request_id, manager_request_context, "Insufficient coverage"
    )

    assert rejected is not None
    assert rejected.status == "rejected"
    assert rejected.approved_by == manager_user_id
    assert rejected.approved_at is not None
    assert rejected.rejection_reason == "Insufficient coverage"


async def test_approve_overtime_request_missing_returns_none(
    service: ApprovalService, manager_request_context: RequestContext
):
    result = await service.approve_overtime_request(uuid.uuid4(), manager_request_context)
    assert result is None


async def test_reject_overtime_request_missing_returns_none(
    service: ApprovalService, manager_request_context: RequestContext
):
    result = await service.reject_overtime_request(uuid.uuid4(), manager_request_context, "No")
    assert result is None


async def test_approve_overtime_request_rejects_non_pending(
    service: ApprovalService,
    overtime_request_service: OvertimeRequestService,
    employee_id: uuid.UUID,
    manager_request_context: RequestContext,
):
    overtime_request_id = await _overtime_request_id(overtime_request_service, employee_id)
    await service.approve_overtime_request(overtime_request_id, manager_request_context)

    with pytest.raises(InvalidApprovalStateError):
        await service.approve_overtime_request(overtime_request_id, manager_request_context)


async def test_reject_overtime_request_rejects_non_pending(
    service: ApprovalService,
    overtime_request_service: OvertimeRequestService,
    employee_id: uuid.UUID,
    manager_request_context: RequestContext,
):
    overtime_request_id = await _overtime_request_id(overtime_request_service, employee_id)
    await service.reject_overtime_request(overtime_request_id, manager_request_context, "No")

    with pytest.raises(InvalidApprovalStateError):
        await service.reject_overtime_request(overtime_request_id, manager_request_context, "No")


async def test_approve_overtime_request_denied_for_non_manager(
    service: ApprovalService,
    overtime_request_service: OvertimeRequestService,
    employee_id: uuid.UUID,
    other_request_context: RequestContext,
):
    overtime_request_id = await _overtime_request_id(overtime_request_service, employee_id)

    with pytest.raises(ApprovalAuthorizationDeniedError):
        await service.approve_overtime_request(overtime_request_id, other_request_context)

    unchanged = await overtime_request_service.get(overtime_request_id)
    assert unchanged is not None
    assert unchanged.status == "pending"


async def test_reject_overtime_request_denied_for_non_manager(
    service: ApprovalService,
    overtime_request_service: OvertimeRequestService,
    employee_id: uuid.UUID,
    other_request_context: RequestContext,
):
    overtime_request_id = await _overtime_request_id(overtime_request_service, employee_id)

    with pytest.raises(ApprovalAuthorizationDeniedError):
        await service.reject_overtime_request(overtime_request_id, other_request_context, "No")

    unchanged = await overtime_request_service.get(overtime_request_id)
    assert unchanged is not None
    assert unchanged.status == "pending"


# --- Timesheet --------------------------------------------------------------


async def test_approve_timesheet(
    service: ApprovalService,
    timesheet_service: TimesheetService,
    employee_id: uuid.UUID,
    manager_user_id: uuid.UUID,
    manager_request_context: RequestContext,
):
    timesheet_id = await _timesheet_id(timesheet_service, employee_id)

    approved = await service.approve_timesheet(timesheet_id, manager_request_context)

    assert approved is not None
    assert approved.status == "approved"
    assert approved.approved_by == manager_user_id
    assert approved.approved_at is not None
    assert approved.rejection_reason is None


async def test_reject_timesheet(
    service: ApprovalService,
    timesheet_service: TimesheetService,
    employee_id: uuid.UUID,
    manager_user_id: uuid.UUID,
    manager_request_context: RequestContext,
):
    timesheet_id = await _timesheet_id(timesheet_service, employee_id)

    rejected = await service.reject_timesheet(
        timesheet_id, manager_request_context, "Insufficient coverage"
    )

    assert rejected is not None
    assert rejected.status == "rejected"
    assert rejected.approved_by == manager_user_id
    assert rejected.approved_at is not None
    assert rejected.rejection_reason == "Insufficient coverage"


async def test_approve_timesheet_missing_returns_none(
    service: ApprovalService, manager_request_context: RequestContext
):
    result = await service.approve_timesheet(uuid.uuid4(), manager_request_context)
    assert result is None


async def test_reject_timesheet_missing_returns_none(
    service: ApprovalService, manager_request_context: RequestContext
):
    result = await service.reject_timesheet(uuid.uuid4(), manager_request_context, "No")
    assert result is None


async def test_approve_timesheet_rejects_non_pending(
    service: ApprovalService,
    timesheet_service: TimesheetService,
    employee_id: uuid.UUID,
    manager_request_context: RequestContext,
):
    timesheet_id = await _timesheet_id(timesheet_service, employee_id)
    await service.approve_timesheet(timesheet_id, manager_request_context)

    with pytest.raises(InvalidApprovalStateError):
        await service.approve_timesheet(timesheet_id, manager_request_context)


async def test_reject_timesheet_rejects_non_pending(
    service: ApprovalService,
    timesheet_service: TimesheetService,
    employee_id: uuid.UUID,
    manager_request_context: RequestContext,
):
    timesheet_id = await _timesheet_id(timesheet_service, employee_id)
    await service.reject_timesheet(timesheet_id, manager_request_context, "No")

    with pytest.raises(InvalidApprovalStateError):
        await service.reject_timesheet(timesheet_id, manager_request_context, "No")


async def test_approve_timesheet_denied_for_non_manager(
    service: ApprovalService,
    timesheet_service: TimesheetService,
    employee_id: uuid.UUID,
    other_request_context: RequestContext,
):
    timesheet_id = await _timesheet_id(timesheet_service, employee_id)

    with pytest.raises(ApprovalAuthorizationDeniedError):
        await service.approve_timesheet(timesheet_id, other_request_context)

    unchanged = await timesheet_service.get(timesheet_id)
    assert unchanged is not None
    assert unchanged.status == "pending"


async def test_reject_timesheet_denied_for_non_manager(
    service: ApprovalService,
    timesheet_service: TimesheetService,
    employee_id: uuid.UUID,
    other_request_context: RequestContext,
):
    timesheet_id = await _timesheet_id(timesheet_service, employee_id)

    with pytest.raises(ApprovalAuthorizationDeniedError):
        await service.reject_timesheet(timesheet_id, other_request_context, "No")

    unchanged = await timesheet_service.get(timesheet_id)
    assert unchanged is not None
    assert unchanged.status == "pending"
