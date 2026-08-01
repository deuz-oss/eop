import uuid
from collections.abc import AsyncGenerator, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.models.employee import Employee
from eop_api.models.organization import Organization
from eop_api.models.project import Project
from eop_api.repositories.employee import EmployeeRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.project import ProjectRepository
from eop_api.schemas.task import TaskCreate, TaskUpdate
from eop_api.services.task import (
    EmployeeNotFoundError,
    OrganizationMismatchError,
    ProjectNotFoundError,
    TaskService,
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
            await conn.execute(text("TRUNCATE TABLE organizations CASCADE"))
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> TaskService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return TaskService(uow_factory)


@pytest.fixture
async def organization(session_factory: Callable[[], AsyncSession]) -> Organization:
    async with session_factory() as session:
        org = await OrganizationRepository(session).create(name="Acme Corp")
        await session.commit()
        session.expunge(org)
        return org


@pytest.fixture
async def other_organization(session_factory: Callable[[], AsyncSession]) -> Organization:
    async with session_factory() as session:
        org = await OrganizationRepository(session).create(name="Globex Corp")
        await session.commit()
        session.expunge(org)
        return org


@pytest.fixture
async def employee(
    session_factory: Callable[[], AsyncSession], organization: Organization
) -> Employee:
    async with session_factory() as session:
        employee = await EmployeeRepository(session).create(
            organization_id=organization.id,
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
        )
        await session.commit()
        session.expunge(employee)
        return employee


@pytest.fixture
async def other_org_employee(
    session_factory: Callable[[], AsyncSession], other_organization: Organization
) -> Employee:
    async with session_factory() as session:
        employee = await EmployeeRepository(session).create(
            organization_id=other_organization.id,
            first_name="Grace",
            last_name="Hopper",
            email="grace@example.com",
        )
        await session.commit()
        session.expunge(employee)
        return employee


@pytest.fixture
async def project(
    session_factory: Callable[[], AsyncSession], organization: Organization
) -> Project:
    async with session_factory() as session:
        project = await ProjectRepository(session).create(
            organization_id=organization.id, name="Apollo", code="APO"
        )
        await session.commit()
        session.expunge(project)
        return project


async def test_create_without_assignee(service: TaskService, project: Project):
    task = await service.create(TaskCreate(project_id=project.id, title="Write report"))

    fetched = await service.get(task.id)

    assert fetched is not None
    assert fetched.title == "Write report"
    assert fetched.project_id == project.id
    assert fetched.assignee_id is None


async def test_create_with_assignee(service: TaskService, project: Project, employee: Employee):
    task = await service.create(
        TaskCreate(project_id=project.id, assignee_id=employee.id, title="Review PR")
    )

    fetched = await service.get(task.id)

    assert fetched is not None
    assert fetched.assignee_id == employee.id


async def test_create_rejects_missing_project(service: TaskService):
    with pytest.raises(ProjectNotFoundError):
        await service.create(TaskCreate(project_id=uuid.uuid4(), title="Orphan"))


async def test_create_rejects_missing_assignee(service: TaskService, project: Project):
    with pytest.raises(EmployeeNotFoundError):
        await service.create(
            TaskCreate(project_id=project.id, assignee_id=uuid.uuid4(), title="Ghost assignee")
        )


async def test_create_rejects_organization_mismatch(
    service: TaskService, project: Project, other_org_employee: Employee
):
    with pytest.raises(OrganizationMismatchError):
        await service.create(
            TaskCreate(project_id=project.id, assignee_id=other_org_employee.id, title="Mismatch")
        )


async def test_get_missing_returns_none(service: TaskService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(service: TaskService, project: Project):
    await service.create(TaskCreate(project_id=project.id, title="Task A"))
    await service.create(TaskCreate(project_id=project.id, title="Task B"))

    items = await service.list()

    assert {"Task A", "Task B"}.issubset({item.title for item in items})


async def test_update_existing(service: TaskService, project: Project):
    task = await service.create(TaskCreate(project_id=project.id, title="Before"))

    updated = await service.update(task.id, TaskUpdate(title="After"))

    assert updated is not None
    assert updated.title == "After"


async def test_update_missing_returns_none(service: TaskService):
    assert await service.update(uuid.uuid4(), TaskUpdate(title="After")) is None


async def test_update_assignee(service: TaskService, project: Project, employee: Employee):
    task = await service.create(TaskCreate(project_id=project.id, title="Unassigned"))

    updated = await service.update(task.id, TaskUpdate(assignee_id=employee.id))

    assert updated is not None
    assert updated.assignee_id == employee.id


async def test_remove_assignee(service: TaskService, project: Project, employee: Employee):
    task = await service.create(
        TaskCreate(project_id=project.id, assignee_id=employee.id, title="Assigned")
    )

    updated = await service.update(task.id, TaskUpdate(assignee_id=None))

    assert updated is not None
    assert updated.assignee_id is None


async def test_update_rejects_missing_assignee(
    service: TaskService, project: Project, employee: Employee
):
    task = await service.create(
        TaskCreate(project_id=project.id, assignee_id=employee.id, title="Assigned")
    )

    with pytest.raises(EmployeeNotFoundError):
        await service.update(task.id, TaskUpdate(assignee_id=uuid.uuid4()))


async def test_update_rejects_missing_project(
    service: TaskService, project: Project, employee: Employee
):
    task = await service.create(TaskCreate(project_id=project.id, title="Task"))

    with pytest.raises(ProjectNotFoundError):
        await service.update(task.id, TaskUpdate(project_id=uuid.uuid4()))


async def test_update_rejects_organization_mismatch(
    service: TaskService, project: Project, other_org_employee: Employee
):
    task = await service.create(TaskCreate(project_id=project.id, title="Task"))

    with pytest.raises(OrganizationMismatchError):
        await service.update(task.id, TaskUpdate(assignee_id=other_org_employee.id))


async def test_delete_existing(service: TaskService, project: Project):
    task = await service.create(TaskCreate(project_id=project.id, title="To delete"))

    deleted = await service.delete(task.id)

    assert deleted is True
    assert await service.get(task.id) is None


async def test_delete_missing_returns_false(service: TaskService):
    assert await service.delete(uuid.uuid4()) is False
