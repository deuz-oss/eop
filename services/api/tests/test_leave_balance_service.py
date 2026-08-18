import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import datetime

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
from eop_api.repositories.leave_balance import LeaveBalanceRepository
from eop_api.repositories.location import LocationRepository
from eop_api.repositories.location_type import LocationTypeRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.position import PositionRepository
from eop_api.repositories.shift import ShiftRepository
from eop_api.repositories.team import TeamRepository
from eop_api.schemas.leave_balance import LeaveBalanceCreate, LeaveBalanceUpdate
from eop_api.schemas.pagination import PaginationParams
from eop_api.services.leave_balance import (
    EmployeeNotFoundError,
    InvalidLeaveBalanceError,
    LeaveBalanceService,
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
def service(session_factory: Callable[[], AsyncSession]) -> LeaveBalanceService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return LeaveBalanceService(uow_factory)


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


def _create(employee_id: uuid.UUID, **overrides) -> LeaveBalanceCreate:
    values = {
        "employee_id": employee_id,
        "period_year": 2026,
        "allocated_days": 12,
    }
    values.update(overrides)
    return LeaveBalanceCreate(**values)


async def test_create_and_get(service: LeaveBalanceService, employee_id: uuid.UUID):
    """A freshly allocated balance always starts `used_days=0`,
    `remaining_days=allocated_days` -- there is no other value it could
    start at, since `used_days`/`remaining_days` are not client-settable."""
    leave_balance = await service.create(_create(employee_id))

    fetched = await service.get(leave_balance.id)

    assert fetched is not None
    assert fetched.employee_id == employee_id
    assert fetched.period_year == 2026
    assert fetched.allocated_days == 12
    assert fetched.used_days == 0
    assert fetched.remaining_days == 12


async def test_create_ignores_client_supplied_used_days(
    service: LeaveBalanceService, employee_id: uuid.UUID
):
    """`LeaveBalanceCreate` has no `used_days` field at all, so a
    client-supplied value in the raw payload is dropped during validation
    before it ever reaches the service -- enforced structurally."""
    data = LeaveBalanceCreate.model_validate(
        {"employee_id": employee_id, "period_year": 2026, "allocated_days": 12, "used_days": 99}
    )

    leave_balance = await service.create(data)

    assert leave_balance.used_days == 0


async def test_create_ignores_client_supplied_remaining_days(
    service: LeaveBalanceService, employee_id: uuid.UUID
):
    data = LeaveBalanceCreate.model_validate(
        {
            "employee_id": employee_id,
            "period_year": 2026,
            "allocated_days": 12,
            "remaining_days": 1,
        }
    )

    leave_balance = await service.create(data)

    assert leave_balance.remaining_days == 12


async def test_create_rejects_missing_employee(service: LeaveBalanceService):
    with pytest.raises(EmployeeNotFoundError):
        await service.create(_create(uuid.uuid4()))


async def test_create_rejects_negative_allocated_days(
    service: LeaveBalanceService, employee_id: uuid.UUID
):
    with pytest.raises(InvalidLeaveBalanceError):
        await service.create(_create(employee_id, allocated_days=-1))


async def test_get_missing_returns_none(service: LeaveBalanceService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(service: LeaveBalanceService, employee_id: uuid.UUID):
    await service.create(_create(employee_id, period_year=2025))
    await service.create(_create(employee_id, period_year=2026))

    items = await service.list()

    assert {2025, 2026}.issubset({item.period_year for item in items})


async def test_update_existing(service: LeaveBalanceService, employee_id: uuid.UUID):
    """`allocated_days` is the only field generic CRUD can still change;
    changing it recomputes `remaining_days` against the persisted
    (untouched) `used_days` server-side."""
    leave_balance = await service.create(_create(employee_id, allocated_days=12))

    updated = await service.update(leave_balance.id, LeaveBalanceUpdate(allocated_days=20))

    assert updated is not None
    assert updated.allocated_days == 20
    assert updated.used_days == 0
    assert updated.remaining_days == 20


async def test_update_missing_returns_none(service: LeaveBalanceService):
    assert await service.update(uuid.uuid4(), LeaveBalanceUpdate(allocated_days=5)) is None


async def test_update_rejects_missing_employee(
    service: LeaveBalanceService, employee_id: uuid.UUID
):
    leave_balance = await service.create(_create(employee_id))

    with pytest.raises(EmployeeNotFoundError):
        await service.update(leave_balance.id, LeaveBalanceUpdate(employee_id=uuid.uuid4()))


async def test_update_ignores_client_supplied_used_days(
    service: LeaveBalanceService, employee_id: uuid.UUID
):
    """`LeaveBalanceUpdate` has no `used_days` field at all -- a
    client-supplied value in the raw payload is dropped during validation,
    and the persisted `used_days` is left untouched."""
    leave_balance = await service.create(_create(employee_id, allocated_days=12))

    data = LeaveBalanceUpdate.model_validate({"used_days": 99})
    updated = await service.update(leave_balance.id, data)

    assert updated is not None
    assert updated.used_days == 0


async def test_update_ignores_client_supplied_remaining_days(
    service: LeaveBalanceService, employee_id: uuid.UUID
):
    leave_balance = await service.create(_create(employee_id, allocated_days=12))

    data = LeaveBalanceUpdate.model_validate({"remaining_days": 1})
    updated = await service.update(leave_balance.id, data)

    assert updated is not None
    assert updated.remaining_days == 12


async def test_update_allocated_days_recomputes_remaining_days_against_persisted_used_days(
    service: LeaveBalanceService,
    session_factory: Callable[[], AsyncSession],
    employee_id: uuid.UUID,
):
    """`used_days` can no longer be set through generic CRUD, so a nonzero
    starting `used_days` is seeded directly via the repository -- exactly
    the state `ApprovalService._sync_leave_balance` would produce -- to
    verify `update` recomputes `remaining_days` against it correctly."""
    async with session_factory() as session:
        balance = await LeaveBalanceRepository(session).create(
            employee_id=employee_id,
            period_year=2026,
            allocated_days=12,
            used_days=4,
            remaining_days=8,
        )
        await session.commit()
        balance_id = balance.id

    updated = await service.update(balance_id, LeaveBalanceUpdate(allocated_days=20))

    assert updated is not None
    assert updated.allocated_days == 20
    assert updated.used_days == 4
    assert updated.remaining_days == 16


async def test_update_rejects_allocated_days_below_persisted_used_days(
    service: LeaveBalanceService,
    session_factory: Callable[[], AsyncSession],
    employee_id: uuid.UUID,
):
    """Lowering `allocated_days` below the persisted `used_days` would drive
    the recomputed `remaining_days` negative -- rejected by the same
    non-negative validation generic CRUD already applies."""
    async with session_factory() as session:
        balance = await LeaveBalanceRepository(session).create(
            employee_id=employee_id,
            period_year=2026,
            allocated_days=12,
            used_days=4,
            remaining_days=8,
        )
        await session.commit()
        balance_id = balance.id

    with pytest.raises(InvalidLeaveBalanceError):
        await service.update(balance_id, LeaveBalanceUpdate(allocated_days=2))


async def test_delete_existing(service: LeaveBalanceService, employee_id: uuid.UUID):
    leave_balance = await service.create(_create(employee_id))

    deleted = await service.delete(leave_balance.id)

    assert deleted is True
    assert await service.get(leave_balance.id) is None


async def test_delete_missing_returns_false(service: LeaveBalanceService):
    assert await service.delete(uuid.uuid4()) is False


async def test_list_paginated_passes_through_offset_and_limit(
    service: LeaveBalanceService, employee_id: uuid.UUID
):
    for i in range(5):
        await service.create(_create(employee_id, period_year=2022 + i))

    page = await service.list_paginated(PaginationParams(offset=1, limit=2))

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2
