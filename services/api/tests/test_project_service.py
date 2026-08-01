import uuid
from collections.abc import AsyncGenerator, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.models.organization import Organization
from eop_api.repositories.organization import OrganizationRepository
from eop_api.schemas.project import ProjectCreate, ProjectUpdate
from eop_api.services.project import (
    DuplicateProjectCodeError,
    OrganizationNotFoundError,
    ProjectService,
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
def service(session_factory: Callable[[], AsyncSession]) -> ProjectService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return ProjectService(uow_factory)


@pytest.fixture
async def organization(session_factory: Callable[[], AsyncSession]) -> Organization:
    async with session_factory() as session:
        org = await OrganizationRepository(session).create(name="Acme Corp")
        await session.commit()
        session.expunge(org)
        return org


async def test_create_and_get(service: ProjectService, organization: Organization):
    project = await service.create(
        ProjectCreate(organization_id=organization.id, name="Apollo", code="APO")
    )

    fetched = await service.get(project.id)

    assert fetched is not None
    assert fetched.name == "Apollo"
    assert fetched.status == "active"


async def test_create_rejects_missing_organization(service: ProjectService):
    with pytest.raises(OrganizationNotFoundError):
        await service.create(ProjectCreate(organization_id=uuid.uuid4(), name="Apollo", code="APO"))


async def test_create_rejects_duplicate_code_in_same_organization(
    service: ProjectService, organization: Organization
):
    await service.create(ProjectCreate(organization_id=organization.id, name="Apollo", code="APO"))

    with pytest.raises(DuplicateProjectCodeError):
        await service.create(
            ProjectCreate(organization_id=organization.id, name="Apollo 2", code="APO")
        )


async def test_get_missing_returns_none(service: ProjectService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(service: ProjectService, organization: Organization):
    await service.create(ProjectCreate(organization_id=organization.id, name="Alpha", code="ALP"))
    await service.create(ProjectCreate(organization_id=organization.id, name="Beta", code="BET"))

    items = await service.list()

    assert {"Alpha", "Beta"}.issubset({item.name for item in items})


async def test_update_existing(service: ProjectService, organization: Organization):
    project = await service.create(
        ProjectCreate(organization_id=organization.id, name="Before", code="BEF")
    )

    updated = await service.update(project.id, ProjectUpdate(name="After"))

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(service: ProjectService):
    assert await service.update(uuid.uuid4(), ProjectUpdate(name="After")) is None


async def test_update_rejects_missing_organization(
    service: ProjectService, organization: Organization
):
    project = await service.create(
        ProjectCreate(organization_id=organization.id, name="Apollo", code="APO")
    )

    with pytest.raises(OrganizationNotFoundError):
        await service.update(project.id, ProjectUpdate(organization_id=uuid.uuid4()))


async def test_update_rejects_duplicate_code_in_same_organization(
    service: ProjectService, organization: Organization
):
    await service.create(ProjectCreate(organization_id=organization.id, name="Apollo", code="APO"))
    other = await service.create(
        ProjectCreate(organization_id=organization.id, name="Zeus", code="ZEU")
    )

    with pytest.raises(DuplicateProjectCodeError):
        await service.update(other.id, ProjectUpdate(code="APO"))


async def test_update_allows_unchanged_code(service: ProjectService, organization: Organization):
    project = await service.create(
        ProjectCreate(organization_id=organization.id, name="Apollo", code="APO")
    )

    updated = await service.update(project.id, ProjectUpdate(code="APO", name="Apollo Renamed"))

    assert updated is not None
    assert updated.name == "Apollo Renamed"


async def test_delete_existing(service: ProjectService, organization: Organization):
    project = await service.create(
        ProjectCreate(organization_id=organization.id, name="To Delete", code="DEL")
    )

    deleted = await service.delete(project.id)

    assert deleted is True
    assert await service.get(project.id) is None


async def test_delete_missing_returns_false(service: ProjectService):
    assert await service.delete(uuid.uuid4()) is False
