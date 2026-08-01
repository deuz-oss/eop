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
from eop_api.schemas.search import SearchParams

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


async def test_paginate_returns_total_and_page_slice(repo: OrganizationRepository):
    for i in range(5):
        await repo.create(name=f"Org {i}")

    page = await repo.paginate(offset=1, limit=2)

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_paginate_defaults(repo: OrganizationRepository):
    for i in range(3):
        await repo.create(name=f"Org {i}")

    page = await repo.paginate()

    assert page.offset == 0
    assert page.limit == 50
    assert page.total == 3
    assert len(page.items) == 3


async def test_paginate_offset_beyond_total_returns_empty(repo: OrganizationRepository):
    await repo.create(name="Only Org")

    page = await repo.paginate(offset=10, limit=10)

    assert page.total == 1
    assert page.items == []


async def test_paginate_search_returns_matching_rows(repo: OrganizationRepository):
    await repo.create(name="Open Robotics")
    await repo.create(name="Closed Systems")

    page = await repo.paginate(search=SearchParams(q="open"))

    assert page.total == 1
    assert [item.name for item in page.items] == ["Open Robotics"]


async def test_paginate_empty_search_returns_all_rows(repo: OrganizationRepository):
    await repo.create(name="Alpha")
    await repo.create(name="Beta")

    page = await repo.paginate(search=SearchParams(q=""))

    assert page.total == 2


async def test_paginate_no_search_returns_all_rows(repo: OrganizationRepository):
    await repo.create(name="Alpha")
    await repo.create(name="Beta")

    page = await repo.paginate(search=None)

    assert page.total == 2


async def test_paginate_search_is_case_insensitive(repo: OrganizationRepository):
    await repo.create(name="Open Robotics")

    page = await repo.paginate(search=SearchParams(q="OPEN"))

    assert page.total == 1
    assert page.items[0].name == "Open Robotics"


async def test_paginate_search_combined_with_offset_and_limit(repo: OrganizationRepository):
    for i in range(5):
        await repo.create(name=f"Open Org {i}")
    await repo.create(name="Closed Org")

    page = await repo.paginate(offset=1, limit=2, search=SearchParams(q="open"))

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2
