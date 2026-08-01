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
from eop_api.repositories.dashboard import DashboardRepository
from eop_api.repositories.employee import EmployeeRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.project import ProjectRepository
from eop_api.repositories.task import TaskRepository

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
def repo(session: AsyncSession) -> DashboardRepository:
    return DashboardRepository(session)


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


async def test_get_counts_organizations(repo: DashboardRepository, organization: Organization):
    counts = await repo.get_counts()

    assert counts.organizations == 1


async def test_get_counts_projects(repo: DashboardRepository, project: Project):
    counts = await repo.get_counts()

    assert counts.projects == 1


async def test_get_counts_employees(repo: DashboardRepository, employee: Employee):
    counts = await repo.get_counts()

    assert counts.employees == 1


async def test_get_counts_assignments(
    repo: DashboardRepository, session: AsyncSession, employee: Employee, project: Project
):
    await AssignmentRepository(session).create(
        employee_id=employee.id,
        project_id=project.id,
        role="Engineer",
        start_date=date(2026, 1, 1),
    )

    counts = await repo.get_counts()

    assert counts.assignments == 1


async def test_get_counts_tasks(repo: DashboardRepository, session: AsyncSession, project: Project):
    await TaskRepository(session).create(project_id=project.id, title="A")
    await TaskRepository(session).create(project_id=project.id, title="B")

    counts = await repo.get_counts()

    assert counts.tasks == 2


async def test_get_counts_reflects_all_entities_together(
    repo: DashboardRepository,
    session: AsyncSession,
    organization: Organization,
    employee: Employee,
    project: Project,
):
    await AssignmentRepository(session).create(
        employee_id=employee.id,
        project_id=project.id,
        role="Engineer",
        start_date=date(2026, 1, 1),
    )
    await TaskRepository(session).create(project_id=project.id, title="A")
    await TaskRepository(session).create(project_id=project.id, title="B")

    counts = await repo.get_counts()

    assert counts.organizations == 1
    assert counts.projects == 1
    assert counts.employees == 1
    assert counts.assignments == 1
    assert counts.tasks == 2


async def test_count_tasks_by_status(
    repo: DashboardRepository, session: AsyncSession, project: Project
):
    task_repo = TaskRepository(session)
    await task_repo.create(project_id=project.id, title="A", status="todo")
    await task_repo.create(project_id=project.id, title="B", status="todo")
    await task_repo.create(project_id=project.id, title="C", status="in_progress")
    await task_repo.create(project_id=project.id, title="D", status="done")

    assert await repo.count_tasks_by_status() == {"todo": 2, "in_progress": 1, "done": 1}


async def test_counts_are_zero_when_empty(repo: DashboardRepository):
    counts = await repo.get_counts()

    assert counts.organizations == 0
    assert counts.projects == 0
    assert counts.employees == 0
    assert counts.assignments == 0
    assert counts.tasks == 0
    assert await repo.count_tasks_by_status() == {}
