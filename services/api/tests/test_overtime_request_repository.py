import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime, time

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.core.security import hash_password
from eop_api.db.base import Base
from eop_api.repositories.department import DepartmentRepository
from eop_api.repositories.employment_status import EmploymentStatusRepository
from eop_api.repositories.employment_type import EmploymentTypeRepository
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.job_grade import JobGradeRepository
from eop_api.repositories.location import LocationRepository
from eop_api.repositories.location_type import LocationTypeRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.overtime_request import OvertimeRequestRepository
from eop_api.repositories.position import PositionRepository
from eop_api.repositories.shift import ShiftRepository
from eop_api.repositories.team import TeamRepository
from eop_api.repositories.user import UserRepository
from eop_api.schemas.search import FilterParams, SearchParams

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def connection() -> AsyncGenerator[AsyncConnection]:
    """A single connection with its own transaction, rolled back after the test.

    The tables are real, migration-managed tables shared with the running
    application, so tests must never commit or drop them. Everything a test does
    happens inside one uncommitted transaction that is discarded on teardown.
    """
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
def repo(session: AsyncSession) -> OvertimeRequestRepository:
    return OvertimeRequestRepository(session)


@pytest.fixture
async def employee_id(session: AsyncSession) -> uuid.UUID:
    """An `HrEmployee` row satisfying every mandatory FK it itself carries.

    OvertimeRequest only needs a valid `HrEmployee.id` to point at -- the full
    Organization/Department/Position/Team/Location/JobGrade/EmploymentType/
    EmploymentStatus/Shift chain below exists solely because `HrEmployee`
    requires it, not because OvertimeRequest cares about any of it.
    """
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


async def test_create_and_get(repo: OvertimeRequestRepository, employee_id: uuid.UUID):
    overtime_request = await repo.create(
        employee_id=employee_id,
        overtime_date=date(2026, 2, 10),
        start_time=time(18, 0),
        end_time=time(20, 0),
    )

    fetched = await repo.get(overtime_request.id)

    assert fetched is not None
    assert fetched.employee_id == employee_id
    assert fetched.overtime_date == date(2026, 2, 10)
    assert fetched.start_time == time(18, 0)
    assert fetched.end_time == time(20, 0)
    assert fetched.status == "pending"
    assert fetched.reason is None


async def test_get_missing_returns_none(repo: OvertimeRequestRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_list_returns_created(repo: OvertimeRequestRepository, employee_id: uuid.UUID):
    await repo.create(
        employee_id=employee_id,
        overtime_date=date(2026, 2, 10),
        start_time=time(18, 0),
        end_time=time(20, 0),
    )
    await repo.create(
        employee_id=employee_id,
        overtime_date=date(2026, 3, 1),
        start_time=time(18, 0),
        end_time=time(20, 0),
    )

    items = await repo.list()

    assert {date(2026, 2, 10), date(2026, 3, 1)}.issubset(
        {item.overtime_date for item in items}
    )


async def test_get_by_employee_returns_only_that_employees_requests(
    repo: OvertimeRequestRepository, session: AsyncSession, employee_id: uuid.UUID
):
    other_organization = await OrganizationRepository(session).create(name="Other Corp")
    other_department = await DepartmentRepository(session).create(
        organization_id=other_organization.id, code="SLS", name="Sales"
    )
    other_position = await PositionRepository(session).create(
        organization_id=other_organization.id,
        department_id=other_department.id,
        code="SLS-1",
        name="Salesperson",
    )
    other_team = await TeamRepository(session).create(
        organization_id=other_organization.id,
        department_id=other_department.id,
        code="FIELD",
        name="Field Team",
    )
    location_type = await LocationTypeRepository(session).create(code="REMOTE", name="Remote")
    location = await LocationRepository(session).create(
        code="RMT", name="Remote", location_type_id=location_type.id
    )
    job_grade = await JobGradeRepository(session).create(code="L2", name="Mid", level=2)
    employment_type = await EmploymentTypeRepository(session).create(code="PT", name="Part-Time")
    employment_status = await EmploymentStatusRepository(session).create(
        code="ACTIVE2", name="Active"
    )
    shift = await ShiftRepository(session).create(
        code="NIGHT",
        name="Night Shift",
        start_time=datetime(2024, 1, 1, 22, 0).time(),
        end_time=datetime(2024, 1, 2, 6, 0).time(),
    )
    other_employee = await HrEmployeeRepository(session).create(
        employee_number="EMP-2",
        first_name="Grace",
        last_name="Hopper",
        full_name="Grace Hopper",
        email="grace@example.com",
        organization_id=other_organization.id,
        department_id=other_department.id,
        position_id=other_position.id,
        team_id=other_team.id,
        location_id=location.id,
        job_grade_id=job_grade.id,
        employment_type_id=employment_type.id,
        employment_status_id=employment_status.id,
        shift_id=shift.id,
        hire_date=datetime(2024, 1, 15).date(),
        employment_status="active",
    )

    mine = await repo.create(
        employee_id=employee_id,
        overtime_date=date(2026, 2, 10),
        start_time=time(18, 0),
        end_time=time(20, 0),
    )
    await repo.create(
        employee_id=other_employee.id,
        overtime_date=date(2026, 2, 11),
        start_time=time(18, 0),
        end_time=time(20, 0),
    )

    items = await repo.get_by_employee(employee_id)

    assert [item.id for item in items] == [mine.id]


async def test_update_existing(repo: OvertimeRequestRepository, employee_id: uuid.UUID):
    overtime_request = await repo.create(
        employee_id=employee_id,
        overtime_date=date(2026, 2, 10),
        start_time=time(18, 0),
        end_time=time(20, 0),
    )

    updated = await repo.update(overtime_request.id, status="approved")

    assert updated is not None
    assert updated.status == "approved"


async def test_update_missing_returns_none(repo: OvertimeRequestRepository):
    assert await repo.update(uuid.uuid4(), status="approved") is None


async def test_delete_existing(repo: OvertimeRequestRepository, employee_id: uuid.UUID):
    overtime_request = await repo.create(
        employee_id=employee_id,
        overtime_date=date(2026, 2, 10),
        start_time=time(18, 0),
        end_time=time(20, 0),
    )

    deleted = await repo.delete(overtime_request.id)

    assert deleted is True
    assert await repo.get(overtime_request.id) is None


async def test_delete_missing_returns_false(repo: OvertimeRequestRepository):
    assert await repo.delete(uuid.uuid4()) is False


async def test_delete_employee_referenced_by_overtime_request_is_restricted(
    repo: OvertimeRequestRepository, session: AsyncSession, employee_id: uuid.UUID
):
    await repo.create(
        employee_id=employee_id,
        overtime_date=date(2026, 2, 10),
        start_time=time(18, 0),
        end_time=time(20, 0),
    )

    with pytest.raises(IntegrityError):
        await HrEmployeeRepository(session).delete(employee_id)


async def test_paginate_returns_total_and_page_slice(
    repo: OvertimeRequestRepository, employee_id: uuid.UUID
):
    for i in range(5):
        await repo.create(
            employee_id=employee_id,
            overtime_date=date(2026, 2, 1 + i),
            start_time=time(18, 0),
            end_time=time(20, 0),
        )

    page = await repo.paginate(offset=1, limit=2)

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_paginate_defaults(repo: OvertimeRequestRepository, employee_id: uuid.UUID):
    for i in range(3):
        await repo.create(
            employee_id=employee_id,
            overtime_date=date(2026, 2, 1 + i),
            start_time=time(18, 0),
            end_time=time(20, 0),
        )

    page = await repo.paginate()

    assert page.offset == 0
    assert page.limit == 50
    assert page.total == 3
    assert len(page.items) == 3


async def test_paginate_search_returns_matching_rows_by_reason(
    repo: OvertimeRequestRepository, employee_id: uuid.UUID
):
    await repo.create(
        employee_id=employee_id,
        overtime_date=date(2026, 2, 10),
        start_time=time(18, 0),
        end_time=time(20, 0),
        reason="Quarter-end close",
    )
    await repo.create(
        employee_id=employee_id,
        overtime_date=date(2026, 3, 1),
        start_time=time(18, 0),
        end_time=time(20, 0),
        reason="Production incident",
    )

    page = await repo.paginate(search=SearchParams(q="close"))

    assert page.total == 1
    assert page.items[0].reason == "Quarter-end close"


async def test_paginate_no_search_returns_all_rows(
    repo: OvertimeRequestRepository, employee_id: uuid.UUID
):
    await repo.create(
        employee_id=employee_id,
        overtime_date=date(2026, 2, 10),
        start_time=time(18, 0),
        end_time=time(20, 0),
    )
    await repo.create(
        employee_id=employee_id,
        overtime_date=date(2026, 3, 1),
        start_time=time(18, 0),
        end_time=time(20, 0),
    )

    page = await repo.paginate(search=None)

    assert page.total == 2


async def test_paginate_filters_by_status(
    repo: OvertimeRequestRepository, employee_id: uuid.UUID
):
    approved = await repo.create(
        employee_id=employee_id,
        overtime_date=date(2026, 2, 10),
        start_time=time(18, 0),
        end_time=time(20, 0),
        status="approved",
    )
    await repo.create(
        employee_id=employee_id,
        overtime_date=date(2026, 3, 1),
        start_time=time(18, 0),
        end_time=time(20, 0),
        status="pending",
    )

    page = await repo.paginate(filters=FilterParams(values={"status": "approved"}))

    assert page.total == 1
    assert page.items[0].id == approved.id


async def test_paginate_filters_by_employee_id(
    repo: OvertimeRequestRepository, session: AsyncSession, employee_id: uuid.UUID
):
    overtime_request = await repo.create(
        employee_id=employee_id,
        overtime_date=date(2026, 2, 10),
        start_time=time(18, 0),
        end_time=time(20, 0),
    )

    page = await repo.paginate(filters=FilterParams(values={"employee_id": employee_id}))

    assert page.total == 1
    assert page.items[0].id == overtime_request.id


async def test_paginate_filters_by_overtime_date(
    repo: OvertimeRequestRepository, employee_id: uuid.UUID
):
    matching = await repo.create(
        employee_id=employee_id,
        overtime_date=date(2026, 2, 10),
        start_time=time(18, 0),
        end_time=time(20, 0),
    )
    await repo.create(
        employee_id=employee_id,
        overtime_date=date(2026, 3, 1),
        start_time=time(18, 0),
        end_time=time(20, 0),
    )

    page = await repo.paginate(
        filters=FilterParams(values={"overtime_date": date(2026, 2, 10)})
    )

    assert page.total == 1
    assert page.items[0].id == matching.id


async def test_paginate_without_filters_returns_all_rows(
    repo: OvertimeRequestRepository, employee_id: uuid.UUID
):
    await repo.create(
        employee_id=employee_id,
        overtime_date=date(2026, 2, 10),
        start_time=time(18, 0),
        end_time=time(20, 0),
    )
    await repo.create(
        employee_id=employee_id,
        overtime_date=date(2026, 3, 1),
        start_time=time(18, 0),
        end_time=time(20, 0),
    )

    page = await repo.paginate()

    assert page.total == 2


async def test_approve_fields_persist(
    repo: OvertimeRequestRepository, session: AsyncSession, employee_id: uuid.UUID
):
    approver = await UserRepository(session).create(
        email="approver@example.com",
        password_hash=hash_password("approver-pass"),
        full_name="Approver",
        is_active=True,
    )
    overtime_request = await repo.create(
        employee_id=employee_id,
        overtime_date=date(2026, 2, 10),
        start_time=time(18, 0),
        end_time=time(20, 0),
    )
    approved_at = datetime(2026, 2, 11, 9, 0, tzinfo=UTC)

    updated = await repo.update(
        overtime_request.id,
        status="approved",
        approved_by=approver.id,
        approved_at=approved_at,
        rejection_reason=None,
    )

    assert updated is not None
    assert updated.status == "approved"
    assert updated.approved_by == approver.id
    assert updated.approved_at == approved_at
    assert updated.rejection_reason is None


async def test_reject_fields_persist(
    repo: OvertimeRequestRepository, session: AsyncSession, employee_id: uuid.UUID
):
    approver = await UserRepository(session).create(
        email="approver@example.com",
        password_hash=hash_password("approver-pass"),
        full_name="Approver",
        is_active=True,
    )
    overtime_request = await repo.create(
        employee_id=employee_id,
        overtime_date=date(2026, 2, 10),
        start_time=time(18, 0),
        end_time=time(20, 0),
    )
    approved_at = datetime(2026, 2, 11, 9, 0, tzinfo=UTC)

    updated = await repo.update(
        overtime_request.id,
        status="rejected",
        approved_by=approver.id,
        approved_at=approved_at,
        rejection_reason="Not enough coverage",
    )

    assert updated is not None
    assert updated.status == "rejected"
    assert updated.approved_by == approver.id
    assert updated.approved_at == approved_at
    assert updated.rejection_reason == "Not enough coverage"
