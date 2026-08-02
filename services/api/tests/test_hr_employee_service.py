import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.exceptions.department import DepartmentOrganizationMismatchError
from eop_api.models.department import Department
from eop_api.models.location import Location
from eop_api.models.location_type import LocationType
from eop_api.models.organization import Organization
from eop_api.models.position import Position
from eop_api.models.team import Team
from eop_api.repositories.department import DepartmentRepository
from eop_api.repositories.location import LocationRepository
from eop_api.repositories.location_type import LocationTypeRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.position import PositionRepository
from eop_api.repositories.team import TeamRepository
from eop_api.schemas.hr_employee import EmployeeCreate, EmployeeUpdate
from eop_api.schemas.pagination import PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.services.hr_employee import (
    DepartmentNotFoundError,
    DuplicateEmployeeEmailError,
    DuplicateEmployeeNumberError,
    HrEmployeeService,
    LocationNotFoundError,
    ManagerNotFoundError,
    OrganizationNotFoundError,
    PositionNotFoundError,
    PositionOrganizationMismatchError,
    SelfManagerError,
    TeamDepartmentMismatchError,
    TeamNotFoundError,
    TeamOrganizationMismatchError,
)
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session_factory() -> AsyncGenerator[Callable[[], AsyncSession]]:
    """A session factory backed by the real (migration-managed) `hr_employees` table.

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
                    "TRUNCATE TABLE hr_employees, teams, positions, locations, "
                    "location_types, departments, organizations CASCADE"
                )
            )
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> HrEmployeeService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return HrEmployeeService(uow_factory)


@pytest.fixture
async def organization(session_factory: Callable[[], AsyncSession]) -> Organization:
    async with session_factory() as session:
        organization = await OrganizationRepository(session).create(name="Acme Corp")
        await session.commit()
        session.expunge(organization)
        return organization


@pytest.fixture
async def other_organization(session_factory: Callable[[], AsyncSession]) -> Organization:
    async with session_factory() as session:
        organization = await OrganizationRepository(session).create(name="Globex Corp")
        await session.commit()
        session.expunge(organization)
        return organization


@pytest.fixture
async def department(
    session_factory: Callable[[], AsyncSession], organization: Organization
) -> Department:
    async with session_factory() as session:
        department = await DepartmentRepository(session).create(
            organization_id=organization.id, code="ENG", name="Engineering"
        )
        await session.commit()
        session.expunge(department)
        return department


@pytest.fixture
async def other_department(
    session_factory: Callable[[], AsyncSession], organization: Organization
) -> Department:
    async with session_factory() as session:
        department = await DepartmentRepository(session).create(
            organization_id=organization.id, code="HR", name="HR"
        )
        await session.commit()
        session.expunge(department)
        return department


@pytest.fixture
async def department_in_other_organization(
    session_factory: Callable[[], AsyncSession], other_organization: Organization
) -> Department:
    async with session_factory() as session:
        department = await DepartmentRepository(session).create(
            organization_id=other_organization.id, code="ENG", name="Engineering (Globex)"
        )
        await session.commit()
        session.expunge(department)
        return department


@pytest.fixture
async def position(
    session_factory: Callable[[], AsyncSession], organization: Organization, department: Department
) -> Position:
    async with session_factory() as session:
        position = await PositionRepository(session).create(
            organization_id=organization.id,
            department_id=department.id,
            code="ENG-1",
            name="Engineer",
        )
        await session.commit()
        session.expunge(position)
        return position


@pytest.fixture
async def position_in_other_organization(
    session_factory: Callable[[], AsyncSession],
    other_organization: Organization,
    department_in_other_organization: Department,
) -> Position:
    async with session_factory() as session:
        position = await PositionRepository(session).create(
            organization_id=other_organization.id,
            department_id=department_in_other_organization.id,
            code="ENG-1",
            name="Engineer (Globex)",
        )
        await session.commit()
        session.expunge(position)
        return position


@pytest.fixture
async def team(
    session_factory: Callable[[], AsyncSession], organization: Organization, department: Department
) -> Team:
    async with session_factory() as session:
        team = await TeamRepository(session).create(
            organization_id=organization.id,
            department_id=department.id,
            code="BACKEND",
            name="Backend",
        )
        await session.commit()
        session.expunge(team)
        return team


@pytest.fixture
async def team_in_other_department(
    session_factory: Callable[[], AsyncSession],
    organization: Organization,
    other_department: Department,
) -> Team:
    async with session_factory() as session:
        team = await TeamRepository(session).create(
            organization_id=organization.id,
            department_id=other_department.id,
            code="HR-OPS",
            name="HR Ops",
        )
        await session.commit()
        session.expunge(team)
        return team


@pytest.fixture
async def team_in_other_organization(
    session_factory: Callable[[], AsyncSession],
    other_organization: Organization,
    department_in_other_organization: Department,
) -> Team:
    async with session_factory() as session:
        team = await TeamRepository(session).create(
            organization_id=other_organization.id,
            department_id=department_in_other_organization.id,
            code="BACKEND",
            name="Backend (Globex)",
        )
        await session.commit()
        session.expunge(team)
        return team


@pytest.fixture
async def location_type(session_factory: Callable[[], AsyncSession]) -> LocationType:
    async with session_factory() as session:
        location_type = await LocationTypeRepository(session).create(name="Office", code="OFFICE")
        await session.commit()
        session.expunge(location_type)
        return location_type


@pytest.fixture
async def location(
    session_factory: Callable[[], AsyncSession], location_type: LocationType
) -> Location:
    async with session_factory() as session:
        location = await LocationRepository(session).create(
            name="HQ", code="HQ", location_type_id=location_type.id
        )
        await session.commit()
        session.expunge(location)
        return location


@pytest.fixture
def create_data(
    organization: Organization,
    department: Department,
    position: Position,
    team: Team,
    location: Location,
) -> Callable[..., EmployeeCreate]:
    def _make(**overrides) -> EmployeeCreate:
        defaults = dict(
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
            hire_date=date(2024, 1, 15),
            employment_status="active",
        )
        defaults.update(overrides)
        return EmployeeCreate(**defaults)

    return _make


async def test_create_and_get(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    employee = await service.create(create_data())

    fetched = await service.get(employee.id)

    assert fetched is not None
    assert fetched.employee_number == "EMP-1"
    assert fetched.full_name == "Ada Lovelace"
    assert fetched.manager_id is None


async def test_create_with_manager(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    manager = await service.create(
        create_data(employee_number="MGR-1", email="grace@example.com", full_name="Grace Hopper")
    )

    report = await service.create(
        create_data(
            employee_number="EMP-2",
            email="alan@example.com",
            full_name="Alan Turing",
            manager_id=manager.id,
        )
    )

    assert report.manager_id == manager.id


async def test_create_rejects_missing_organization(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    with pytest.raises(OrganizationNotFoundError):
        await service.create(create_data(organization_id=uuid.uuid4()))


async def test_create_rejects_missing_department(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    with pytest.raises(DepartmentNotFoundError):
        await service.create(create_data(department_id=uuid.uuid4()))


async def test_create_rejects_department_in_different_organization(
    service: HrEmployeeService,
    create_data: Callable[..., EmployeeCreate],
    department_in_other_organization: Department,
):
    with pytest.raises(DepartmentOrganizationMismatchError):
        await service.create(create_data(department_id=department_in_other_organization.id))


async def test_create_rejects_missing_position(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    with pytest.raises(PositionNotFoundError):
        await service.create(create_data(position_id=uuid.uuid4()))


async def test_create_rejects_position_in_different_organization(
    service: HrEmployeeService,
    create_data: Callable[..., EmployeeCreate],
    position_in_other_organization: Position,
):
    with pytest.raises(PositionOrganizationMismatchError):
        await service.create(create_data(position_id=position_in_other_organization.id))


async def test_create_rejects_missing_team(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    with pytest.raises(TeamNotFoundError):
        await service.create(create_data(team_id=uuid.uuid4()))


async def test_create_rejects_team_in_different_organization(
    service: HrEmployeeService,
    create_data: Callable[..., EmployeeCreate],
    team_in_other_organization: Team,
):
    with pytest.raises(TeamOrganizationMismatchError):
        await service.create(create_data(team_id=team_in_other_organization.id))


async def test_create_rejects_team_in_different_department(
    service: HrEmployeeService,
    create_data: Callable[..., EmployeeCreate],
    team_in_other_department: Team,
):
    with pytest.raises(TeamDepartmentMismatchError):
        await service.create(create_data(team_id=team_in_other_department.id))


async def test_create_rejects_missing_location(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    with pytest.raises(LocationNotFoundError):
        await service.create(create_data(location_id=uuid.uuid4()))


async def test_create_rejects_missing_manager(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    with pytest.raises(ManagerNotFoundError):
        await service.create(create_data(manager_id=uuid.uuid4()))


async def test_create_rejects_duplicate_employee_number(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    await service.create(create_data())

    with pytest.raises(DuplicateEmployeeNumberError):
        await service.create(create_data(email="other@example.com"))


async def test_create_rejects_duplicate_email(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    await service.create(create_data())

    with pytest.raises(DuplicateEmployeeEmailError):
        await service.create(create_data(employee_number="EMP-2"))


async def test_get_missing_returns_none(service: HrEmployeeService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    await service.create(create_data())
    await service.create(
        create_data(employee_number="EMP-2", email="alan@example.com", full_name="Alan Turing")
    )

    items = await service.list()

    assert {"Ada Lovelace", "Alan Turing"}.issubset({item.full_name for item in items})


async def test_update_existing(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    employee = await service.create(create_data())

    updated = await service.update(employee.id, EmployeeUpdate(full_name="Ada Byron"))

    assert updated is not None
    assert updated.full_name == "Ada Byron"


async def test_update_missing_returns_none(service: HrEmployeeService):
    assert await service.update(uuid.uuid4(), EmployeeUpdate(full_name="Nobody")) is None


async def test_update_rejects_missing_organization(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    employee = await service.create(create_data())

    with pytest.raises(OrganizationNotFoundError):
        await service.update(employee.id, EmployeeUpdate(organization_id=uuid.uuid4()))


async def test_update_rejects_missing_department(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    employee = await service.create(create_data())

    with pytest.raises(DepartmentNotFoundError):
        await service.update(employee.id, EmployeeUpdate(department_id=uuid.uuid4()))


async def test_update_rejects_department_in_different_organization(
    service: HrEmployeeService,
    create_data: Callable[..., EmployeeCreate],
    department_in_other_organization: Department,
):
    employee = await service.create(create_data())

    with pytest.raises(DepartmentOrganizationMismatchError):
        await service.update(
            employee.id, EmployeeUpdate(department_id=department_in_other_organization.id)
        )


async def test_update_rejects_missing_position(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    employee = await service.create(create_data())

    with pytest.raises(PositionNotFoundError):
        await service.update(employee.id, EmployeeUpdate(position_id=uuid.uuid4()))


async def test_update_rejects_position_in_different_organization(
    service: HrEmployeeService,
    create_data: Callable[..., EmployeeCreate],
    position_in_other_organization: Position,
):
    employee = await service.create(create_data())

    with pytest.raises(PositionOrganizationMismatchError):
        await service.update(
            employee.id, EmployeeUpdate(position_id=position_in_other_organization.id)
        )


async def test_update_rejects_missing_team(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    employee = await service.create(create_data())

    with pytest.raises(TeamNotFoundError):
        await service.update(employee.id, EmployeeUpdate(team_id=uuid.uuid4()))


async def test_update_rejects_team_in_different_organization(
    service: HrEmployeeService,
    create_data: Callable[..., EmployeeCreate],
    team_in_other_organization: Team,
):
    employee = await service.create(create_data())

    with pytest.raises(TeamOrganizationMismatchError):
        await service.update(employee.id, EmployeeUpdate(team_id=team_in_other_organization.id))


async def test_update_rejects_team_in_different_department(
    service: HrEmployeeService,
    create_data: Callable[..., EmployeeCreate],
    team_in_other_department: Team,
):
    employee = await service.create(create_data())

    with pytest.raises(TeamDepartmentMismatchError):
        await service.update(employee.id, EmployeeUpdate(team_id=team_in_other_department.id))


async def test_update_rejects_missing_location(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    employee = await service.create(create_data())

    with pytest.raises(LocationNotFoundError):
        await service.update(employee.id, EmployeeUpdate(location_id=uuid.uuid4()))


async def test_update_rejects_missing_manager(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    employee = await service.create(create_data())

    with pytest.raises(ManagerNotFoundError):
        await service.update(employee.id, EmployeeUpdate(manager_id=uuid.uuid4()))


async def test_update_accepts_existing_manager(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    manager = await service.create(
        create_data(employee_number="MGR-1", email="grace@example.com", full_name="Grace Hopper")
    )
    employee = await service.create(
        create_data(employee_number="EMP-2", email="alan@example.com", full_name="Alan Turing")
    )

    updated = await service.update(employee.id, EmployeeUpdate(manager_id=manager.id))

    assert updated is not None
    assert updated.manager_id == manager.id


async def test_update_rejects_self_manager(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    employee = await service.create(create_data())

    with pytest.raises(SelfManagerError):
        await service.update(employee.id, EmployeeUpdate(manager_id=employee.id))


async def test_update_rejects_duplicate_employee_number(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    await service.create(create_data())
    other = await service.create(
        create_data(employee_number="EMP-2", email="alan@example.com", full_name="Alan Turing")
    )

    with pytest.raises(DuplicateEmployeeNumberError):
        await service.update(other.id, EmployeeUpdate(employee_number="EMP-1"))


async def test_update_rejects_duplicate_email(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    await service.create(create_data())
    other = await service.create(
        create_data(employee_number="EMP-2", email="alan@example.com", full_name="Alan Turing")
    )

    with pytest.raises(DuplicateEmployeeEmailError):
        await service.update(other.id, EmployeeUpdate(email="ada@example.com"))


async def test_update_allows_unchanged_employee_number_and_email(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    employee = await service.create(create_data())

    updated = await service.update(
        employee.id,
        EmployeeUpdate(employee_number="EMP-1", email="ada@example.com", full_name="Ada Byron"),
    )

    assert updated is not None
    assert updated.full_name == "Ada Byron"


async def test_update_organization_without_touching_department_rejects_now_mismatched_department(
    service: HrEmployeeService,
    create_data: Callable[..., EmployeeCreate],
    other_organization: Organization,
):
    """The effective department is always validated against the effective
    organization, even when `department_id` itself is absent from this
    update -- an employee must never end up pointing at a department in
    another organization."""
    employee = await service.create(create_data())

    with pytest.raises(DepartmentOrganizationMismatchError):
        await service.update(employee.id, EmployeeUpdate(organization_id=other_organization.id))


async def test_update_unrelated_field_revalidates_existing_references_without_error(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    """An update that touches none of the reference fields still re-validates
    the (unchanged, already-consistent) effective references, and must not
    raise."""
    employee = await service.create(create_data())

    updated = await service.update(employee.id, EmployeeUpdate(full_name="Ada Byron"))

    assert updated is not None
    assert updated.full_name == "Ada Byron"
    assert updated.department_id == employee.department_id


async def test_delete_existing(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    employee = await service.create(create_data())

    deleted = await service.delete(employee.id)

    assert deleted is True
    assert await service.get(employee.id) is None


async def test_delete_missing_returns_false(service: HrEmployeeService):
    assert await service.delete(uuid.uuid4()) is False


async def test_delete_manager_with_reports_is_restricted(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    manager = await service.create(
        create_data(employee_number="MGR-1", email="grace@example.com", full_name="Grace Hopper")
    )
    await service.create(
        create_data(
            employee_number="EMP-2",
            email="alan@example.com",
            full_name="Alan Turing",
            manager_id=manager.id,
        )
    )

    with pytest.raises(IntegrityError):
        await service.delete(manager.id)


async def test_list_paginated_passes_through_offset_and_limit(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    for i in range(5):
        await service.create(create_data(employee_number=f"EMP-{i}", email=f"emp{i}@example.com"))

    page = await service.list_paginated(PaginationParams(offset=1, limit=2))

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_list_paginated_passes_through_search(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    await service.create(create_data())
    await service.create(
        create_data(
            employee_number="EMP-2",
            first_name="Alan",
            last_name="Turing",
            email="alan@example.com",
            full_name="Alan Turing",
        )
    )

    page = await service.list_paginated(
        PaginationParams(offset=0, limit=50), SearchParams(q="lovelace")
    )

    assert page.total == 1
    assert page.items[0].full_name == "Ada Lovelace"


async def test_list_paginated_passes_through_filters(
    service: HrEmployeeService, create_data: Callable[..., EmployeeCreate]
):
    await service.create(create_data())
    await service.create(
        create_data(
            employee_number="EMP-2",
            email="alan@example.com",
            full_name="Alan Turing",
            employment_status="terminated",
        )
    )

    page = await service.list_paginated(
        PaginationParams(offset=0, limit=50),
        filters=FilterParams(values={"employment_status": "active"}),
    )

    assert page.total == 1
    assert page.items[0].employment_status == "active"
