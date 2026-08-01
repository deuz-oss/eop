import uuid
from collections.abc import AsyncGenerator
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.models.employee import Employee
from eop_api.models.organization import Organization
from eop_api.models.project import Project
from eop_api.repositories.assignment import AssignmentRepository
from eop_api.repositories.employee import EmployeeRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.project import ProjectRepository

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
def repo(session: AsyncSession) -> AssignmentRepository:
    return AssignmentRepository(session)


@pytest.fixture
async def organization(session: AsyncSession) -> Organization:
    return await OrganizationRepository(session).create(name="Acme Corp")


@pytest.fixture
async def employee(session: AsyncSession, organization: Organization) -> Employee:
    return await EmployeeRepository(session).create(
        organization_id=organization.id,
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
    )


@pytest.fixture
async def project(session: AsyncSession, organization: Organization) -> Project:
    return await ProjectRepository(session).create(
        organization_id=organization.id, name="Apollo", code="APO"
    )


async def test_create_and_get(repo: AssignmentRepository, employee: Employee, project: Project):
    assignment = await repo.create(
        employee_id=employee.id,
        project_id=project.id,
        role="Engineer",
        start_date=date(2026, 1, 1),
    )

    fetched = await repo.get(assignment.id)

    assert fetched is not None
    assert fetched.employee_id == employee.id
    assert fetched.project_id == project.id
    assert fetched.role == "Engineer"


async def test_get_missing_returns_none(repo: AssignmentRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_list_returns_created(
    repo: AssignmentRepository,
    session: AsyncSession,
    organization: Organization,
    employee: Employee,
    project: Project,
):
    other_project = await ProjectRepository(session).create(
        organization_id=organization.id, name="Zeus", code="ZEU"
    )
    await repo.create(
        employee_id=employee.id,
        project_id=project.id,
        role="Engineer",
        start_date=date(2026, 1, 1),
    )
    await repo.create(
        employee_id=employee.id,
        project_id=other_project.id,
        role="Lead",
        start_date=date(2026, 1, 1),
    )

    items = await repo.list()

    assert {"Engineer", "Lead"}.issubset({item.role for item in items})


async def test_update_existing(repo: AssignmentRepository, employee: Employee, project: Project):
    assignment = await repo.create(
        employee_id=employee.id,
        project_id=project.id,
        role="Before",
        start_date=date(2026, 1, 1),
    )

    updated = await repo.update(assignment.id, role="After")

    assert updated is not None
    assert updated.role == "After"


async def test_update_missing_returns_none(repo: AssignmentRepository):
    assert await repo.update(uuid.uuid4(), role="After") is None


async def test_delete_existing(repo: AssignmentRepository, employee: Employee, project: Project):
    assignment = await repo.create(
        employee_id=employee.id,
        project_id=project.id,
        role="Engineer",
        start_date=date(2026, 1, 1),
    )

    deleted = await repo.delete(assignment.id)

    assert deleted is True
    assert await repo.get(assignment.id) is None


async def test_delete_missing_returns_false(repo: AssignmentRepository):
    assert await repo.delete(uuid.uuid4()) is False


async def test_exists(repo: AssignmentRepository, employee: Employee, project: Project):
    assignment = await repo.create(
        employee_id=employee.id,
        project_id=project.id,
        role="Engineer",
        start_date=date(2026, 1, 1),
    )

    assert await repo.exists(assignment.id) is True
    assert await repo.exists(uuid.uuid4()) is False


async def test_count(
    repo: AssignmentRepository,
    session: AsyncSession,
    organization: Organization,
    employee: Employee,
    project: Project,
):
    other_project = await ProjectRepository(session).create(
        organization_id=organization.id, name="Zeus", code="ZEU"
    )
    other_employee = await EmployeeRepository(session).create(
        organization_id=organization.id,
        first_name="Grace",
        last_name="Hopper",
        email="grace@example.com",
    )
    await repo.create(
        employee_id=employee.id, project_id=project.id, role="A", start_date=date(2026, 1, 1)
    )
    await repo.create(
        employee_id=employee.id,
        project_id=other_project.id,
        role="B",
        start_date=date(2026, 1, 1),
    )
    await repo.create(
        employee_id=other_employee.id,
        project_id=project.id,
        role="C",
        start_date=date(2026, 1, 1),
    )

    assert await repo.count() == 3


async def test_get_by_employee_and_project(
    repo: AssignmentRepository, employee: Employee, project: Project
):
    assignment = await repo.create(
        employee_id=employee.id,
        project_id=project.id,
        role="Engineer",
        start_date=date(2026, 1, 1),
    )

    found = await repo.get_by_employee_and_project(employee.id, project.id)

    assert found is not None
    assert found.id == assignment.id
    assert await repo.get_by_employee_and_project(employee.id, uuid.uuid4()) is None
