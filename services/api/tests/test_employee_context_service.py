from collections.abc import AsyncGenerator, Callable
from datetime import date, time

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
from eop_api.repositories.job_grade import JobGradeRepository
from eop_api.repositories.location import LocationRepository
from eop_api.repositories.location_type import LocationTypeRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.position import PositionRepository
from eop_api.repositories.shift import ShiftRepository
from eop_api.repositories.team import TeamRepository
from eop_api.repositories.user import UserRepository
from eop_api.schemas.hr_employee import EmployeeCreate
from eop_api.services.employee_context import (
    EmployeeContext,
    EmployeeContextNotFoundError,
    EmployeeContextResolver,
    MultipleEmployeeContextError,
)
from eop_api.services.hr_employee import HrEmployeeService
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session_factory() -> AsyncGenerator[Callable[[], AsyncSession]]:
    """A session factory backed by the real (migration-managed) tables.

    Both `EmployeeContextResolver` and `HrEmployeeService` commit internally
    (each owns its own transaction boundary via a UoW), so rows are
    truncated after each test instead of relying on a rolled-back
    transaction.
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
                    "location_types, departments, organizations, job_grades, "
                    "employment_types, employment_statuses, shifts, users CASCADE"
                )
            )
        await engine.dispose()


@pytest.fixture
def uow_factory(
    session_factory: Callable[[], AsyncSession],
) -> Callable[[], SQLAlchemyUnitOfWork]:
    return lambda: SQLAlchemyUnitOfWork(session_factory)


@pytest.fixture
def resolver(uow_factory: Callable[[], SQLAlchemyUnitOfWork]) -> EmployeeContextResolver:
    return EmployeeContextResolver(uow_factory)


@pytest.fixture
def hr_employee_service(uow_factory: Callable[[], SQLAlchemyUnitOfWork]) -> HrEmployeeService:
    return HrEmployeeService(uow_factory)


@pytest.fixture
async def organization(session_factory: Callable[[], AsyncSession]) -> Organization:
    async with session_factory() as session:
        organization = await OrganizationRepository(session).create(name="Acme Corp")
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
async def job_grade(session_factory: Callable[[], AsyncSession]) -> JobGrade:
    async with session_factory() as session:
        job_grade = await JobGradeRepository(session).create(code="L1", name="Engineer I", level=1)
        await session.commit()
        session.expunge(job_grade)
        return job_grade


@pytest.fixture
async def employment_type(session_factory: Callable[[], AsyncSession]) -> EmploymentType:
    async with session_factory() as session:
        employment_type = await EmploymentTypeRepository(session).create(
            code="FT", name="Full-Time"
        )
        await session.commit()
        session.expunge(employment_type)
        return employment_type


@pytest.fixture
async def employment_status(session_factory: Callable[[], AsyncSession]) -> EmploymentStatus:
    async with session_factory() as session:
        employment_status = await EmploymentStatusRepository(session).create(
            code="ACTIVE", name="Active"
        )
        await session.commit()
        session.expunge(employment_status)
        return employment_status


@pytest.fixture
async def shift(session_factory: Callable[[], AsyncSession]) -> Shift:
    async with session_factory() as session:
        shift = await ShiftRepository(session).create(
            code="DAY", name="Day Shift", start_time=time(9, 0), end_time=time(17, 0)
        )
        await session.commit()
        session.expunge(shift)
        return shift


@pytest.fixture
async def user(session_factory: Callable[[], AsyncSession]) -> User:
    async with session_factory() as session:
        user = await UserRepository(session).create(
            email="linked@example.com",
            password_hash="hashed",
            full_name="Linked User",
            is_active=True,
        )
        await session.commit()
        session.expunge(user)
        return user


@pytest.fixture
def create_data(
    organization: Organization,
    department: Department,
    position: Position,
    team: Team,
    location: Location,
    job_grade: JobGrade,
    employment_type: EmploymentType,
    employment_status: EmploymentStatus,
    shift: Shift,
) -> Callable[..., EmployeeCreate]:
    def _make(**overrides: object) -> EmployeeCreate:
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
            job_grade_id=job_grade.id,
            employment_type_id=employment_type.id,
            employment_status_id=employment_status.id,
            shift_id=shift.id,
            hire_date=date(2024, 1, 15),
            employment_status="active",
        )
        defaults.update(overrides)
        return EmployeeCreate(**defaults)

    return _make


async def test_resolve_returns_employee_context_for_single_linked_employee(
    resolver: EmployeeContextResolver,
    hr_employee_service: HrEmployeeService,
    create_data: Callable[..., EmployeeCreate],
    user: User,
):
    employee = await hr_employee_service.create(create_data(user_id=user.id))

    context = await resolver.resolve(user)

    assert isinstance(context, EmployeeContext)
    assert context.user.id == user.id
    assert context.employee.id == employee.id


async def test_resolve_raises_not_found_when_no_employee_is_linked(
    resolver: EmployeeContextResolver, user: User
):
    with pytest.raises(EmployeeContextNotFoundError):
        await resolver.resolve(user)


async def test_resolve_raises_multiple_when_two_employees_share_user_id(
    resolver: EmployeeContextResolver,
    hr_employee_service: HrEmployeeService,
    create_data: Callable[..., EmployeeCreate],
    user: User,
):
    await hr_employee_service.create(
        create_data(employee_number="EMP-1", email="ada@example.com", user_id=user.id)
    )
    await hr_employee_service.create(
        create_data(employee_number="EMP-2", email="alan@example.com", user_id=user.id)
    )

    with pytest.raises(MultipleEmployeeContextError):
        await resolver.resolve(user)
