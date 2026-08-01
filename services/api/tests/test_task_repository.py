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
def repo(session: AsyncSession) -> TaskRepository:
    return TaskRepository(session)


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


async def test_create_and_get(repo: TaskRepository, project: Project):
    task = await repo.create(project_id=project.id, title="Write report")

    fetched = await repo.get(task.id)

    assert fetched is not None
    assert fetched.project_id == project.id
    assert fetched.title == "Write report"
    assert fetched.assignee_id is None
    assert fetched.status == "todo"


async def test_create_with_assignee(repo: TaskRepository, project: Project, employee: Employee):
    task = await repo.create(project_id=project.id, assignee_id=employee.id, title="Review PR")

    fetched = await repo.get(task.id)

    assert fetched is not None
    assert fetched.assignee_id == employee.id


async def test_get_missing_returns_none(repo: TaskRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_list_returns_created(repo: TaskRepository, project: Project):
    await repo.create(project_id=project.id, title="Task A")
    await repo.create(project_id=project.id, title="Task B")

    items = await repo.list()

    assert {"Task A", "Task B"}.issubset({item.title for item in items})


async def test_update_existing(repo: TaskRepository, project: Project):
    task = await repo.create(project_id=project.id, title="Before")

    updated = await repo.update(task.id, title="After")

    assert updated is not None
    assert updated.title == "After"


async def test_update_missing_returns_none(repo: TaskRepository):
    assert await repo.update(uuid.uuid4(), title="After") is None


async def test_delete_existing(repo: TaskRepository, project: Project):
    task = await repo.create(project_id=project.id, title="To delete")

    deleted = await repo.delete(task.id)

    assert deleted is True
    assert await repo.get(task.id) is None


async def test_delete_missing_returns_false(repo: TaskRepository):
    assert await repo.delete(uuid.uuid4()) is False


async def test_exists(repo: TaskRepository, project: Project):
    task = await repo.create(project_id=project.id, title="Exists")

    assert await repo.exists(task.id) is True
    assert await repo.exists(uuid.uuid4()) is False


async def test_count(
    repo: TaskRepository, session: AsyncSession, organization: Organization, project: Project
):
    other_project = await ProjectRepository(session).create(
        organization_id=organization.id, name="Zeus", code="ZEU"
    )
    await repo.create(project_id=project.id, title="A")
    await repo.create(project_id=project.id, title="B")
    await repo.create(project_id=other_project.id, title="C")

    assert await repo.count() == 3


async def test_list_by_project(
    repo: TaskRepository, session: AsyncSession, organization: Organization, project: Project
):
    other_project = await ProjectRepository(session).create(
        organization_id=organization.id, name="Zeus", code="ZEU"
    )
    await repo.create(project_id=project.id, title="A")
    await repo.create(project_id=project.id, title="B")
    await repo.create(project_id=other_project.id, title="C")

    items = await repo.list_by_project(project.id)

    assert {item.title for item in items} == {"A", "B"}


async def test_list_by_assignee(
    repo: TaskRepository,
    session: AsyncSession,
    organization: Organization,
    project: Project,
    employee: Employee,
):
    other_employee = await EmployeeRepository(session).create(
        organization_id=organization.id,
        first_name="Grace",
        last_name="Hopper",
        email="grace@example.com",
    )
    await repo.create(project_id=project.id, assignee_id=employee.id, title="A")
    await repo.create(project_id=project.id, assignee_id=employee.id, title="B")
    await repo.create(project_id=project.id, assignee_id=other_employee.id, title="C")

    items = await repo.list_by_assignee(employee.id)

    assert {item.title for item in items} == {"A", "B"}


async def test_create_with_status_and_due_date(repo: TaskRepository, project: Project):
    task = await repo.create(
        project_id=project.id, title="Scheduled", status="in_progress", due_date=date(2026, 3, 1)
    )

    fetched = await repo.get(task.id)

    assert fetched is not None
    assert fetched.status == "in_progress"
    assert fetched.due_date == date(2026, 3, 1)
