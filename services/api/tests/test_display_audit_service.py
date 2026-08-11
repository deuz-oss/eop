import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
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
from eop_api.repositories.store import StoreRepository
from eop_api.repositories.store_type import StoreTypeRepository
from eop_api.repositories.team import TeamRepository
from eop_api.repositories.visit import VisitRepository
from eop_api.schemas.display_audit import DisplayAuditCreate, DisplayAuditUpdate
from eop_api.schemas.pagination import PaginationParams
from eop_api.services.display_audit import (
    DisplayAuditAuthorizationDeniedError,
    DisplayAuditService,
    VisitNotFoundError,
)
from eop_api.services.employee_context import EmployeeContext, RequestContext
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
                    "store_types CASCADE"
                )
            )
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> DisplayAuditService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return DisplayAuditService(uow_factory)


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
async def visit_id(
    session_factory: Callable[[], AsyncSession], employee_id: uuid.UUID
) -> uuid.UUID:
    async with session_factory() as session:
        organization = await OrganizationRepository(session).create(name="Store Org")
        store_type = await StoreTypeRepository(session).create(code="MT", name="Modern Trade")
        store = await StoreRepository(session).create(
            code="ST-1",
            name="Indomaret Sudirman",
            organization_id=organization.id,
            store_type_id=store_type.id,
        )
        visit = await VisitRepository(session).create(
            employee_id=employee_id,
            store_id=store.id,
            visited_at=datetime(2026, 1, 5, 9, 0, tzinfo=UTC),
        )
        await session.commit()
        return visit.id


@pytest.fixture
async def other_visit_id(
    session_factory: Callable[[], AsyncSession], other_employee_id: uuid.UUID
) -> uuid.UUID:
    async with session_factory() as session:
        organization = await OrganizationRepository(session).create(name="Other Store Org")
        store_type = await StoreTypeRepository(session).create(code="GT", name="General Trade")
        store = await StoreRepository(session).create(
            code="ST-2",
            name="Alfamart Thamrin",
            organization_id=organization.id,
            store_type_id=store_type.id,
        )
        visit = await VisitRepository(session).create(
            employee_id=other_employee_id,
            store_id=store.id,
            visited_at=datetime(2026, 1, 6, 9, 0, tzinfo=UTC),
        )
        await session.commit()
        return visit.id


def _request_context(employee_id: uuid.UUID) -> RequestContext:
    """A `RequestContext` built entirely in memory, scoped to `employee_id`.

    Only `employee_context.employee.id` is read by
    `VisitAuthorizationEvaluator`/`DisplayAuditService`, so the `User`/
    `HrEmployee` here need not be persisted -- mirrors
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


def _create(visit_id: uuid.UUID, **overrides) -> DisplayAuditCreate:
    values = {
        "visit_id": visit_id,
        "display_area": "Main Shelf",
        "observation": "Compliant",
    }
    values.update(overrides)
    return DisplayAuditCreate(**values)


async def test_create_and_get(
    service: DisplayAuditService, employee_id: uuid.UUID, visit_id: uuid.UUID
):
    context = _request_context(employee_id)
    audit = await service.create(_create(visit_id), context)

    fetched = await service.get(audit.id, context)

    assert fetched is not None
    assert fetched.visit_id == visit_id
    assert fetched.display_area == "Main Shelf"


async def test_create_rejects_missing_visit(service: DisplayAuditService, employee_id: uuid.UUID):
    with pytest.raises(VisitNotFoundError):
        await service.create(_create(uuid.uuid4()), _request_context(employee_id))


async def test_create_denied_for_non_owner(
    service: DisplayAuditService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    visit_id: uuid.UUID,
):
    with pytest.raises(DisplayAuditAuthorizationDeniedError):
        await service.create(_create(visit_id), _request_context(other_employee_id))


async def test_create_allows_multiple_per_visit(
    service: DisplayAuditService, employee_id: uuid.UUID, visit_id: uuid.UUID
):
    context = _request_context(employee_id)
    first = await service.create(_create(visit_id, display_area="Main Shelf"), context)
    second = await service.create(_create(visit_id, display_area="Window Display"), context)

    assert first.id != second.id


async def test_get_missing_returns_none(service: DisplayAuditService, employee_id: uuid.UUID):
    assert await service.get(uuid.uuid4(), _request_context(employee_id)) is None


async def test_get_denied_for_non_owner(
    service: DisplayAuditService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    visit_id: uuid.UUID,
):
    owner_context = _request_context(employee_id)
    audit = await service.create(_create(visit_id), owner_context)

    with pytest.raises(DisplayAuditAuthorizationDeniedError):
        await service.get(audit.id, _request_context(other_employee_id))


async def test_list_returns_only_owned(
    service: DisplayAuditService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    visit_id: uuid.UUID,
    other_visit_id: uuid.UUID,
):
    context = _request_context(employee_id)
    other_context = _request_context(other_employee_id)
    await service.create(_create(visit_id), context)
    await service.create(_create(other_visit_id), other_context)

    items = await service.list(context)

    assert {item.visit_id for item in items} == {visit_id}


async def test_list_paginated_returns_only_owned(
    service: DisplayAuditService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    visit_id: uuid.UUID,
    other_visit_id: uuid.UUID,
):
    context = _request_context(employee_id)
    other_context = _request_context(other_employee_id)
    await service.create(_create(visit_id), context)
    await service.create(_create(other_visit_id), other_context)

    page = await service.list_paginated(context, PaginationParams(offset=0, limit=50))

    assert page.total == 1
    assert page.items[0].visit_id == visit_id


async def test_update_existing(
    service: DisplayAuditService, employee_id: uuid.UUID, visit_id: uuid.UUID
):
    context = _request_context(employee_id)
    audit = await service.create(_create(visit_id), context)

    updated = await service.update(audit.id, DisplayAuditUpdate(notes="Updated"), context)

    assert updated is not None
    assert updated.notes == "Updated"
    assert updated.display_area == "Main Shelf"


async def test_update_missing_returns_none(service: DisplayAuditService, employee_id: uuid.UUID):
    assert (
        await service.update(
            uuid.uuid4(), DisplayAuditUpdate(notes="x"), _request_context(employee_id)
        )
        is None
    )


async def test_update_denied_for_non_owner(
    service: DisplayAuditService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    visit_id: uuid.UUID,
):
    owner_context = _request_context(employee_id)
    audit = await service.create(_create(visit_id), owner_context)

    with pytest.raises(DisplayAuditAuthorizationDeniedError):
        await service.update(
            audit.id, DisplayAuditUpdate(notes="x"), _request_context(other_employee_id)
        )


async def test_delete_existing(
    service: DisplayAuditService, employee_id: uuid.UUID, visit_id: uuid.UUID
):
    context = _request_context(employee_id)
    audit = await service.create(_create(visit_id), context)

    deleted = await service.delete(audit.id, context)

    assert deleted is True
    assert await service.get(audit.id, context) is None


async def test_delete_missing_returns_false(service: DisplayAuditService, employee_id: uuid.UUID):
    assert await service.delete(uuid.uuid4(), _request_context(employee_id)) is False


async def test_delete_denied_for_non_owner(
    service: DisplayAuditService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    visit_id: uuid.UUID,
):
    owner_context = _request_context(employee_id)
    audit = await service.create(_create(visit_id), owner_context)

    with pytest.raises(DisplayAuditAuthorizationDeniedError):
        await service.delete(audit.id, _request_context(other_employee_id))

    assert await service.get(audit.id, owner_context) is not None


async def test_authorization_follows_current_visit_owner(
    service: DisplayAuditService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    visit_id: uuid.UUID,
    session_factory: Callable[[], AsyncSession],
):
    """If the parent Visit's `employee_id` is reassigned, DisplayAudit
    authorization must follow the new owner -- not a copied/stale value,
    since this entity carries no `employee_id` of its own."""
    owner_context = _request_context(employee_id)
    audit = await service.create(_create(visit_id), owner_context)

    async with session_factory() as session:
        await VisitRepository(session).update(visit_id, employee_id=other_employee_id)
        await session.commit()

    other_context = _request_context(other_employee_id)
    fetched = await service.get(audit.id, other_context)
    assert fetched is not None

    with pytest.raises(DisplayAuditAuthorizationDeniedError):
        await service.get(audit.id, owner_context)
