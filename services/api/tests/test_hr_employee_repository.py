import uuid
from collections.abc import AsyncGenerator
from datetime import date, time

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
from eop_api.db.base import Base
from eop_api.models.department import Department
from eop_api.models.employment_status import EmploymentStatus
from eop_api.models.employment_type import EmploymentType
from eop_api.models.job_grade import JobGrade
from eop_api.models.location import Location
from eop_api.models.location_type import LocationType
from eop_api.models.organization import Organization
from eop_api.models.position import Position
from eop_api.models.shift import Shift
from eop_api.models.team import Team
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
def repo(session: AsyncSession) -> HrEmployeeRepository:
    return HrEmployeeRepository(session)


@pytest.fixture
async def organization(session: AsyncSession) -> Organization:
    return await OrganizationRepository(session).create(name="Acme Corp")


@pytest.fixture
async def other_organization(session: AsyncSession) -> Organization:
    return await OrganizationRepository(session).create(name="Globex Corp")


@pytest.fixture
async def department(session: AsyncSession, organization: Organization) -> Department:
    return await DepartmentRepository(session).create(
        organization_id=organization.id, code="ENG", name="Engineering"
    )


@pytest.fixture
async def position(
    session: AsyncSession, organization: Organization, department: Department
) -> Position:
    return await PositionRepository(session).create(
        organization_id=organization.id, department_id=department.id, code="ENG-1", name="Engineer"
    )


@pytest.fixture
async def team(session: AsyncSession, organization: Organization, department: Department) -> Team:
    return await TeamRepository(session).create(
        organization_id=organization.id, department_id=department.id, code="BACKEND", name="Backend"
    )


@pytest.fixture
async def location_type(session: AsyncSession) -> LocationType:
    return await LocationTypeRepository(session).create(name="Office", code="OFFICE")


@pytest.fixture
async def location(session: AsyncSession, location_type: LocationType) -> Location:
    return await LocationRepository(session).create(
        name="HQ", code="HQ", location_type_id=location_type.id
    )


@pytest.fixture
async def job_grade(session: AsyncSession) -> JobGrade:
    return await JobGradeRepository(session).create(code="L1", name="Engineer I", level=1)


@pytest.fixture
async def employment_type(session: AsyncSession) -> EmploymentType:
    return await EmploymentTypeRepository(session).create(code="FT", name="Full-Time")


@pytest.fixture
async def employment_status(session: AsyncSession) -> EmploymentStatus:
    return await EmploymentStatusRepository(session).create(code="ACTIVE", name="Active")


@pytest.fixture
async def shift(session: AsyncSession) -> Shift:
    return await ShiftRepository(session).create(
        code="DAY",
        name="Day Shift",
        start_time=time(9, 0),
        end_time=time(17, 0),
    )


@pytest.fixture
async def user(session: AsyncSession) -> User:
    return await UserRepository(session).create(
        email="linked@example.com",
        password_hash="hashed",
        full_name="Linked User",
        is_active=True,
    )


@pytest.fixture
def employee_kwargs(
    organization: Organization,
    department: Department,
    position: Position,
    team: Team,
    location: Location,
    job_grade: JobGrade,
    employment_type: EmploymentType,
    employment_status: EmploymentStatus,
    shift: Shift,
) -> dict:
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
        "hire_date": date(2024, 1, 15),
        "employment_status": "active",
    }


async def test_create_and_get(repo: HrEmployeeRepository, employee_kwargs: dict):
    employee = await repo.create(
        employee_number="EMP-1",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        **employee_kwargs,
    )

    fetched = await repo.get(employee.id)

    assert fetched is not None
    assert fetched.employee_number == "EMP-1"
    assert fetched.full_name == "Ada Lovelace"
    assert fetched.email == "ada@example.com"
    assert fetched.manager_id is None


async def test_create_with_manager(repo: HrEmployeeRepository, employee_kwargs: dict):
    manager = await repo.create(
        employee_number="MGR-1",
        first_name="Grace",
        last_name="Hopper",
        full_name="Grace Hopper",
        email="grace@example.com",
        **employee_kwargs,
    )

    report = await repo.create(
        employee_number="EMP-2",
        first_name="Alan",
        last_name="Turing",
        full_name="Alan Turing",
        email="alan@example.com",
        manager_id=manager.id,
        **employee_kwargs,
    )

    fetched = await repo.get(report.id)

    assert fetched is not None
    assert fetched.manager_id == manager.id


async def test_create_persists_job_grade_id(repo: HrEmployeeRepository, employee_kwargs: dict):
    employee = await repo.create(
        employee_number="EMP-1",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        **employee_kwargs,
    )

    assert employee.job_grade_id == employee_kwargs["job_grade_id"]


async def test_get_retrieves_job_grade_id(repo: HrEmployeeRepository, employee_kwargs: dict):
    employee = await repo.create(
        employee_number="EMP-1",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        **employee_kwargs,
    )

    fetched = await repo.get(employee.id)

    assert fetched is not None
    assert fetched.job_grade_id == employee_kwargs["job_grade_id"]


async def test_create_persists_employment_type_id(
    repo: HrEmployeeRepository, employee_kwargs: dict
):
    employee = await repo.create(
        employee_number="EMP-1",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        **employee_kwargs,
    )

    assert employee.employment_type_id == employee_kwargs["employment_type_id"]


async def test_get_retrieves_employment_type_id(
    repo: HrEmployeeRepository, employee_kwargs: dict
):
    employee = await repo.create(
        employee_number="EMP-1",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        **employee_kwargs,
    )

    fetched = await repo.get(employee.id)

    assert fetched is not None
    assert fetched.employment_type_id == employee_kwargs["employment_type_id"]


async def test_create_persists_employment_status_id(
    repo: HrEmployeeRepository, employee_kwargs: dict
):
    employee = await repo.create(
        employee_number="EMP-1",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        **employee_kwargs,
    )

    assert employee.employment_status_id == employee_kwargs["employment_status_id"]


async def test_get_retrieves_employment_status_id(
    repo: HrEmployeeRepository, employee_kwargs: dict
):
    employee = await repo.create(
        employee_number="EMP-1",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        **employee_kwargs,
    )

    fetched = await repo.get(employee.id)

    assert fetched is not None
    assert fetched.employment_status_id == employee_kwargs["employment_status_id"]


async def test_create_persists_shift_id(repo: HrEmployeeRepository, employee_kwargs: dict):
    employee = await repo.create(
        employee_number="EMP-1",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        **employee_kwargs,
    )

    assert employee.shift_id == employee_kwargs["shift_id"]


async def test_get_retrieves_shift_id(repo: HrEmployeeRepository, employee_kwargs: dict):
    employee = await repo.create(
        employee_number="EMP-1",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        **employee_kwargs,
    )

    fetched = await repo.get(employee.id)

    assert fetched is not None
    assert fetched.shift_id == employee_kwargs["shift_id"]


async def test_get_missing_returns_none(repo: HrEmployeeRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_list_returns_created(repo: HrEmployeeRepository, employee_kwargs: dict):
    await repo.create(
        employee_number="EMP-1",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        **employee_kwargs,
    )
    await repo.create(
        employee_number="EMP-2",
        first_name="Alan",
        last_name="Turing",
        full_name="Alan Turing",
        email="alan@example.com",
        **employee_kwargs,
    )

    items = await repo.list()

    assert {"Ada Lovelace", "Alan Turing"}.issubset({item.full_name for item in items})


async def test_update_existing(repo: HrEmployeeRepository, employee_kwargs: dict):
    employee = await repo.create(
        employee_number="EMP-1",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        **employee_kwargs,
    )

    updated = await repo.update(employee.id, full_name="Ada Byron")

    assert updated is not None
    assert updated.full_name == "Ada Byron"


async def test_update_missing_returns_none(repo: HrEmployeeRepository):
    assert await repo.update(uuid.uuid4(), full_name="Nobody") is None


async def test_delete_existing(repo: HrEmployeeRepository, employee_kwargs: dict):
    employee = await repo.create(
        employee_number="EMP-1",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        **employee_kwargs,
    )

    deleted = await repo.delete(employee.id)

    assert deleted is True
    assert await repo.get(employee.id) is None


async def test_delete_missing_returns_false(repo: HrEmployeeRepository):
    assert await repo.delete(uuid.uuid4()) is False


async def test_delete_manager_with_reports_is_restricted(
    repo: HrEmployeeRepository, employee_kwargs: dict
):
    manager = await repo.create(
        employee_number="MGR-1",
        first_name="Grace",
        last_name="Hopper",
        full_name="Grace Hopper",
        email="grace@example.com",
        **employee_kwargs,
    )
    await repo.create(
        employee_number="EMP-2",
        first_name="Alan",
        last_name="Turing",
        full_name="Alan Turing",
        email="alan@example.com",
        manager_id=manager.id,
        **employee_kwargs,
    )

    with pytest.raises(IntegrityError):
        await repo.delete(manager.id)


async def test_delete_job_grade_referenced_by_employee_is_restricted(
    session: AsyncSession, repo: HrEmployeeRepository, employee_kwargs: dict, job_grade: JobGrade
):
    await repo.create(
        employee_number="EMP-1",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        **employee_kwargs,
    )

    with pytest.raises(IntegrityError):
        await JobGradeRepository(session).delete(job_grade.id)


async def test_delete_employment_type_referenced_by_employee_is_restricted(
    session: AsyncSession,
    repo: HrEmployeeRepository,
    employee_kwargs: dict,
    employment_type: EmploymentType,
):
    await repo.create(
        employee_number="EMP-1",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        **employee_kwargs,
    )

    with pytest.raises(IntegrityError):
        await EmploymentTypeRepository(session).delete(employment_type.id)


async def test_delete_employment_status_referenced_by_employee_is_restricted(
    session: AsyncSession,
    repo: HrEmployeeRepository,
    employee_kwargs: dict,
    employment_status: EmploymentStatus,
):
    await repo.create(
        employee_number="EMP-1",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        **employee_kwargs,
    )

    with pytest.raises(IntegrityError):
        await EmploymentStatusRepository(session).delete(employment_status.id)


async def test_delete_shift_referenced_by_employee_is_restricted(
    session: AsyncSession,
    repo: HrEmployeeRepository,
    employee_kwargs: dict,
    shift: Shift,
):
    await repo.create(
        employee_number="EMP-1",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        **employee_kwargs,
    )

    with pytest.raises(IntegrityError):
        await ShiftRepository(session).delete(shift.id)


async def test_get_by_employee_number(repo: HrEmployeeRepository, employee_kwargs: dict):
    employee = await repo.create(
        employee_number="EMP-1",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        **employee_kwargs,
    )

    found = await repo.get_by_employee_number("EMP-1")

    assert found is not None
    assert found.id == employee.id
    assert await repo.get_by_employee_number("missing") is None


async def test_get_by_email(repo: HrEmployeeRepository, employee_kwargs: dict):
    employee = await repo.create(
        employee_number="EMP-1",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        **employee_kwargs,
    )

    found = await repo.get_by_email("ada@example.com")

    assert found is not None
    assert found.id == employee.id
    assert await repo.get_by_email("missing@example.com") is None


async def test_get_by_user_id_returns_linked_employee(
    repo: HrEmployeeRepository, employee_kwargs: dict, user: User
):
    employee = await repo.create(
        employee_number="EMP-1",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        user_id=user.id,
        **employee_kwargs,
    )

    found = await repo.get_by_user_id(user.id)

    assert [item.id for item in found] == [employee.id]


async def test_get_by_user_id_missing_returns_empty_sequence(repo: HrEmployeeRepository):
    found = await repo.get_by_user_id(uuid.uuid4())

    assert list(found) == []


async def test_get_by_user_id_returns_sequence_for_multiple_employees_sharing_user_id(
    repo: HrEmployeeRepository, employee_kwargs: dict, user: User
):
    """`user_id` has no uniqueness constraint (cardinality is an unresolved
    business decision, per `docs/architecture/PR-050_DISCOVERY.md` Step 2) --
    this verifies `get_by_user_id` returns every matching row as a `Sequence`
    instead of raising `MultipleResultsFound`, which `BaseRepository.get_by()`
    would do here.
    """
    first = await repo.create(
        employee_number="EMP-1",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        user_id=user.id,
        **employee_kwargs,
    )
    second = await repo.create(
        employee_number="EMP-2",
        first_name="Alan",
        last_name="Turing",
        full_name="Alan Turing",
        email="alan@example.com",
        user_id=user.id,
        **employee_kwargs,
    )

    found = await repo.get_by_user_id(user.id)

    assert {item.id for item in found} == {first.id, second.id}


async def test_paginate_returns_total_and_page_slice(
    repo: HrEmployeeRepository, employee_kwargs: dict
):
    for i in range(5):
        await repo.create(
            employee_number=f"EMP-{i}",
            first_name=f"First{i}",
            last_name="Last",
            full_name=f"First{i} Last",
            email=f"emp{i}@example.com",
            **employee_kwargs,
        )

    page = await repo.paginate(offset=1, limit=2)

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_paginate_defaults(repo: HrEmployeeRepository, employee_kwargs: dict):
    for i in range(3):
        await repo.create(
            employee_number=f"EMP-{i}",
            first_name=f"First{i}",
            last_name="Last",
            full_name=f"First{i} Last",
            email=f"emp{i}@example.com",
            **employee_kwargs,
        )

    page = await repo.paginate()

    assert page.offset == 0
    assert page.limit == 50
    assert page.total == 3
    assert len(page.items) == 3


async def test_paginate_search_by_employee_number(
    repo: HrEmployeeRepository, employee_kwargs: dict
):
    await repo.create(
        employee_number="ENG-ALPHA",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        **employee_kwargs,
    )
    await repo.create(
        employee_number="ENG-BETA",
        first_name="Alan",
        last_name="Turing",
        full_name="Alan Turing",
        email="alan@example.com",
        **employee_kwargs,
    )

    page = await repo.paginate(search=SearchParams(q="alpha"))

    assert page.total == 1
    assert page.items[0].employee_number == "ENG-ALPHA"


async def test_paginate_search_by_full_name(repo: HrEmployeeRepository, employee_kwargs: dict):
    await repo.create(
        employee_number="EMP-1",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        **employee_kwargs,
    )
    await repo.create(
        employee_number="EMP-2",
        first_name="Alan",
        last_name="Turing",
        full_name="Alan Turing",
        email="alan@example.com",
        **employee_kwargs,
    )

    page = await repo.paginate(search=SearchParams(q="lovelace"))

    assert page.total == 1
    assert page.items[0].full_name == "Ada Lovelace"


async def test_paginate_search_by_email(repo: HrEmployeeRepository, employee_kwargs: dict):
    await repo.create(
        employee_number="EMP-1",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        **employee_kwargs,
    )
    await repo.create(
        employee_number="EMP-2",
        first_name="Alan",
        last_name="Turing",
        full_name="Alan Turing",
        email="alan@example.com",
        **employee_kwargs,
    )

    page = await repo.paginate(search=SearchParams(q="alan@"))

    assert page.total == 1
    assert page.items[0].email == "alan@example.com"


async def test_paginate_no_search_returns_all_rows(
    repo: HrEmployeeRepository, employee_kwargs: dict
):
    await repo.create(
        employee_number="EMP-1",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        **employee_kwargs,
    )
    await repo.create(
        employee_number="EMP-2",
        first_name="Alan",
        last_name="Turing",
        full_name="Alan Turing",
        email="alan@example.com",
        **employee_kwargs,
    )

    page = await repo.paginate(search=None)

    assert page.total == 2


async def test_paginate_filters_by_organization_id(
    session: AsyncSession,
    repo: HrEmployeeRepository,
    employee_kwargs: dict,
    other_organization: Organization,
    job_grade: JobGrade,
    employment_type: EmploymentType,
    employment_status: EmploymentStatus,
    shift: Shift,
):
    other_department = await DepartmentRepository(session).create(
        organization_id=other_organization.id, code="ENG", name="Engineering (Globex)"
    )
    other_position = await PositionRepository(session).create(
        organization_id=other_organization.id,
        department_id=other_department.id,
        code="ENG-1",
        name="Engineer",
    )
    other_team = await TeamRepository(session).create(
        organization_id=other_organization.id,
        department_id=other_department.id,
        code="BE",
        name="Backend",
    )
    other_location_type = await LocationTypeRepository(session).create(name="Remote", code="REMOTE")
    other_location = await LocationRepository(session).create(
        name="Remote HQ", code="REMOTE-HQ", location_type_id=other_location_type.id
    )

    await repo.create(
        employee_number="EMP-1",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        **employee_kwargs,
    )
    await repo.create(
        employee_number="EMP-2",
        first_name="Alan",
        last_name="Turing",
        full_name="Alan Turing",
        email="alan@example.com",
        organization_id=other_organization.id,
        department_id=other_department.id,
        position_id=other_position.id,
        team_id=other_team.id,
        location_id=other_location.id,
        job_grade_id=job_grade.id,
        employment_type_id=employment_type.id,
        employment_status_id=employment_status.id,
        shift_id=shift.id,
        hire_date=employee_kwargs["hire_date"],
        employment_status="active",
    )

    page = await repo.paginate(
        filters=FilterParams(values={"organization_id": employee_kwargs["organization_id"]})
    )

    assert page.total == 1
    assert page.items[0].organization_id == employee_kwargs["organization_id"]


async def test_paginate_filters_by_employment_status(
    repo: HrEmployeeRepository, employee_kwargs: dict
):
    active_kwargs = dict(employee_kwargs)
    active_kwargs["employment_status"] = "active"
    inactive_kwargs = dict(employee_kwargs)
    inactive_kwargs["employment_status"] = "terminated"

    await repo.create(
        employee_number="EMP-1",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        **active_kwargs,
    )
    await repo.create(
        employee_number="EMP-2",
        first_name="Alan",
        last_name="Turing",
        full_name="Alan Turing",
        email="alan@example.com",
        **inactive_kwargs,
    )

    page = await repo.paginate(filters=FilterParams(values={"employment_status": "active"}))

    assert page.total == 1
    assert page.items[0].employment_status == "active"
