import uuid
from collections.abc import AsyncGenerator

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
from eop_api.models.organization import Organization
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
def repo(session: AsyncSession) -> ProjectRepository:
    return ProjectRepository(session)


@pytest.fixture
async def organization(session: AsyncSession) -> Organization:
    return await OrganizationRepository(session).create(name="Acme Corp")


async def test_create_and_get(repo: ProjectRepository, organization: Organization):
    project = await repo.create(organization_id=organization.id, name="Apollo", code="APO")

    fetched = await repo.get(project.id)

    assert fetched is not None
    assert fetched.name == "Apollo"
    assert fetched.code == "APO"
    assert fetched.organization_id == organization.id


async def test_get_missing_returns_none(repo: ProjectRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_list_returns_created(repo: ProjectRepository, organization: Organization):
    await repo.create(organization_id=organization.id, name="Alpha", code="ALP")
    await repo.create(organization_id=organization.id, name="Beta", code="BET")

    items = await repo.list()

    assert {"Alpha", "Beta"}.issubset({item.name for item in items})


async def test_update_existing(repo: ProjectRepository, organization: Organization):
    project = await repo.create(organization_id=organization.id, name="Before", code="BEF")

    updated = await repo.update(project.id, name="After")

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(repo: ProjectRepository):
    assert await repo.update(uuid.uuid4(), name="After") is None


async def test_delete_existing(repo: ProjectRepository, organization: Organization):
    project = await repo.create(organization_id=organization.id, name="To Delete", code="DEL")

    deleted = await repo.delete(project.id)

    assert deleted is True
    assert await repo.get(project.id) is None


async def test_delete_missing_returns_false(repo: ProjectRepository):
    assert await repo.delete(uuid.uuid4()) is False


async def test_exists(repo: ProjectRepository, organization: Organization):
    project = await repo.create(organization_id=organization.id, name="Exists", code="EXI")

    assert await repo.exists(project.id) is True
    assert await repo.exists(uuid.uuid4()) is False


async def test_count(repo: ProjectRepository, organization: Organization):
    await repo.create(organization_id=organization.id, name="A", code="A")
    await repo.create(organization_id=organization.id, name="B", code="B")
    await repo.create(organization_id=organization.id, name="C", code="C")

    assert await repo.count() == 3


async def test_get_by_organization_and_code(repo: ProjectRepository, organization: Organization):
    project = await repo.create(organization_id=organization.id, name="Apollo", code="APO")

    found = await repo.get_by_organization_and_code(organization.id, "APO")

    assert found is not None
    assert found.id == project.id
    assert await repo.get_by_organization_and_code(organization.id, "MISSING") is None
