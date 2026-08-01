import uuid
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
from eop_api.repositories.employee import EmployeeRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.project import ProjectRepository
from eop_api.schemas.assignment import AssignmentCreate, AssignmentUpdate
from eop_api.services.assignment import (
    AssignmentService,
    DuplicateAssignmentError,
    EmployeeNotFoundError,
    OrganizationMismatchError,
    ProjectNotFoundError,
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
def service(session_factory: Callable[[], AsyncSession]) -> AssignmentService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return AssignmentService(uow_factory)


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


@pytest.fixture
async def other_org_project(
    session_factory: Callable[[], AsyncSession], other_organization: Organization
) -> Project:
    async with session_factory() as session:
        project = await ProjectRepository(session).create(
            organization_id=other_organization.id, name="Zeus", code="ZEU"
        )
        await session.commit()
        session.expunge(project)
        return project


async def test_create_and_get(service: AssignmentService, employee: Employee, project: Project):
    assignment = await service.create(
        AssignmentCreate(
            employee_id=employee.id,
            project_id=project.id,
            role="Engineer",
            start_date=date(2026, 1, 1),
        )
    )

    fetched = await service.get(assignment.id)

    assert fetched is not None
    assert fetched.role == "Engineer"
    assert fetched.employee_id == employee.id
    assert fetched.project_id == project.id


async def test_create_rejects_missing_employee(service: AssignmentService, project: Project):
    with pytest.raises(EmployeeNotFoundError):
        await service.create(
            AssignmentCreate(
                employee_id=uuid.uuid4(),
                project_id=project.id,
                role="Engineer",
                start_date=date(2026, 1, 1),
            )
        )


async def test_create_rejects_missing_project(service: AssignmentService, employee: Employee):
    with pytest.raises(ProjectNotFoundError):
        await service.create(
            AssignmentCreate(
                employee_id=employee.id,
                project_id=uuid.uuid4(),
                role="Engineer",
                start_date=date(2026, 1, 1),
            )
        )


async def test_create_rejects_organization_mismatch(
    service: AssignmentService, employee: Employee, other_org_project: Project
):
    with pytest.raises(OrganizationMismatchError):
        await service.create(
            AssignmentCreate(
                employee_id=employee.id,
                project_id=other_org_project.id,
                role="Engineer",
                start_date=date(2026, 1, 1),
            )
        )


async def test_create_rejects_duplicate_assignment(
    service: AssignmentService, employee: Employee, project: Project
):
    await service.create(
        AssignmentCreate(
            employee_id=employee.id,
            project_id=project.id,
            role="Engineer",
            start_date=date(2026, 1, 1),
        )
    )

    with pytest.raises(DuplicateAssignmentError):
        await service.create(
            AssignmentCreate(
                employee_id=employee.id,
                project_id=project.id,
                role="Lead",
                start_date=date(2026, 1, 1),
            )
        )


async def test_get_missing_returns_none(service: AssignmentService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(
    service: AssignmentService,
    session_factory: Callable[[], AsyncSession],
    organization: Organization,
    employee: Employee,
    project: Project,
):
    async with session_factory() as session:
        other_project = await ProjectRepository(session).create(
            organization_id=organization.id, name="Zeus", code="ZEU"
        )
        await session.commit()
        session.expunge(other_project)

    await service.create(
        AssignmentCreate(
            employee_id=employee.id,
            project_id=project.id,
            role="Engineer",
            start_date=date(2026, 1, 1),
        )
    )
    await service.create(
        AssignmentCreate(
            employee_id=employee.id,
            project_id=other_project.id,
            role="Lead",
            start_date=date(2026, 1, 1),
        )
    )

    items = await service.list()

    assert {"Engineer", "Lead"}.issubset({item.role for item in items})


async def test_update_existing(service: AssignmentService, employee: Employee, project: Project):
    assignment = await service.create(
        AssignmentCreate(
            employee_id=employee.id,
            project_id=project.id,
            role="Before",
            start_date=date(2026, 1, 1),
        )
    )

    updated = await service.update(assignment.id, AssignmentUpdate(role="After"))

    assert updated is not None
    assert updated.role == "After"


async def test_update_missing_returns_none(service: AssignmentService):
    assert await service.update(uuid.uuid4(), AssignmentUpdate(role="After")) is None


async def test_update_rejects_missing_employee(
    service: AssignmentService, employee: Employee, project: Project
):
    assignment = await service.create(
        AssignmentCreate(
            employee_id=employee.id,
            project_id=project.id,
            role="Engineer",
            start_date=date(2026, 1, 1),
        )
    )

    with pytest.raises(EmployeeNotFoundError):
        await service.update(assignment.id, AssignmentUpdate(employee_id=uuid.uuid4()))


async def test_update_rejects_missing_project(
    service: AssignmentService, employee: Employee, project: Project
):
    assignment = await service.create(
        AssignmentCreate(
            employee_id=employee.id,
            project_id=project.id,
            role="Engineer",
            start_date=date(2026, 1, 1),
        )
    )

    with pytest.raises(ProjectNotFoundError):
        await service.update(assignment.id, AssignmentUpdate(project_id=uuid.uuid4()))


async def test_update_rejects_organization_mismatch(
    service: AssignmentService,
    employee: Employee,
    project: Project,
    other_org_project: Project,
):
    assignment = await service.create(
        AssignmentCreate(
            employee_id=employee.id,
            project_id=project.id,
            role="Engineer",
            start_date=date(2026, 1, 1),
        )
    )

    with pytest.raises(OrganizationMismatchError):
        await service.update(assignment.id, AssignmentUpdate(project_id=other_org_project.id))


async def test_update_rejects_duplicate_assignment(
    service: AssignmentService,
    session_factory: Callable[[], AsyncSession],
    organization: Organization,
    employee: Employee,
    project: Project,
):
    async with session_factory() as session:
        other_project = await ProjectRepository(session).create(
            organization_id=organization.id, name="Zeus", code="ZEU"
        )
        await session.commit()
        session.expunge(other_project)

    await service.create(
        AssignmentCreate(
            employee_id=employee.id,
            project_id=project.id,
            role="Engineer",
            start_date=date(2026, 1, 1),
        )
    )
    other = await service.create(
        AssignmentCreate(
            employee_id=employee.id,
            project_id=other_project.id,
            role="Lead",
            start_date=date(2026, 1, 1),
        )
    )

    with pytest.raises(DuplicateAssignmentError):
        await service.update(other.id, AssignmentUpdate(project_id=project.id))


async def test_update_allows_unchanged_assignment(
    service: AssignmentService, employee: Employee, project: Project
):
    assignment = await service.create(
        AssignmentCreate(
            employee_id=employee.id,
            project_id=project.id,
            role="Engineer",
            start_date=date(2026, 1, 1),
        )
    )

    updated = await service.update(
        assignment.id,
        AssignmentUpdate(employee_id=employee.id, project_id=project.id, role="Lead"),
    )

    assert updated is not None
    assert updated.role == "Lead"


async def test_delete_existing(service: AssignmentService, employee: Employee, project: Project):
    assignment = await service.create(
        AssignmentCreate(
            employee_id=employee.id,
            project_id=project.id,
            role="Engineer",
            start_date=date(2026, 1, 1),
        )
    )

    deleted = await service.delete(assignment.id)

    assert deleted is True
    assert await service.get(assignment.id) is None


async def test_delete_missing_returns_false(service: AssignmentService):
    assert await service.delete(uuid.uuid4()) is False
