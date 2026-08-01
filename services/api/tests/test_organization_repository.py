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
from eop_api.repositories.organization import OrganizationRepository

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
def repo(session: AsyncSession) -> OrganizationRepository:
    return OrganizationRepository(session)


async def test_create_and_get(repo: OrganizationRepository):
    organization = await repo.create(name="Acme Corp")

    fetched = await repo.get(organization.id)

    assert fetched is not None
    assert fetched.name == "Acme Corp"


async def test_get_missing_returns_none(repo: OrganizationRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_list_returns_created(repo: OrganizationRepository):
    await repo.create(name="Alpha")
    await repo.create(name="Beta")

    items = await repo.list()

    assert {"Alpha", "Beta"}.issubset({item.name for item in items})


async def test_update_existing(repo: OrganizationRepository):
    organization = await repo.create(name="Before")

    updated = await repo.update(organization.id, name="After")

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(repo: OrganizationRepository):
    assert await repo.update(uuid.uuid4(), name="After") is None


async def test_delete_existing(repo: OrganizationRepository):
    organization = await repo.create(name="To Delete")

    deleted = await repo.delete(organization.id)

    assert deleted is True
    assert await repo.get(organization.id) is None


async def test_delete_missing_returns_false(repo: OrganizationRepository):
    assert await repo.delete(uuid.uuid4()) is False
