from collections.abc import AsyncGenerator, Callable
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
from eop_api.repositories.task import TaskRepository
from eop_api.services.dashboard import DashboardService
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
def service(session_factory: Callable[[], AsyncSession]) -> DashboardService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return DashboardService(uow_factory)


@pytest.fixture
async def organization(session_factory: Callable[[], AsyncSession]) -> Organization:
    async with session_factory() as session:
        org = await OrganizationRepository(session).create(name="Acme Corp")
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


async def test_get_stats_empty(service: DashboardService):
    stats = await service.get_stats()

    assert stats.organizations == 0
    assert stats.projects == 0
    assert stats.employees == 0
    assert stats.assignments == 0
    assert stats.tasks == 0
    assert stats.tasks_by_status == {}


async def test_get_stats_returns_aggregate_structure(
    service: DashboardService,
    session_factory: Callable[[], AsyncSession],
    organization: Organization,
    employee: Employee,
    project: Project,
):
    async with session_factory() as session:
        await AssignmentRepository(session).create(
            employee_id=employee.id,
            project_id=project.id,
            role="Engineer",
            start_date=date(2026, 1, 1),
        )
        task_repo = TaskRepository(session)
        await task_repo.create(project_id=project.id, title="A", status="todo")
        await task_repo.create(project_id=project.id, title="B", status="done")
        await session.commit()

    stats = await service.get_stats()

    assert stats.organizations == 1
    assert stats.projects == 1
    assert stats.employees == 1
    assert stats.assignments == 1
    assert stats.tasks == 2
    assert stats.tasks_by_status == {"todo": 1, "done": 1}
