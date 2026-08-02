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
from eop_api.repositories.employment_status import EmploymentStatusRepository
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
def repo(session: AsyncSession) -> EmploymentStatusRepository:
    return EmploymentStatusRepository(session)


async def test_create_and_get(repo: EmploymentStatusRepository):
    employment_status = await repo.create(code="ACTIVE", name="Active")

    fetched = await repo.get(employment_status.id)

    assert fetched is not None
    assert fetched.code == "ACTIVE"
    assert fetched.name == "Active"
    assert fetched.description is None


async def test_get_missing_returns_none(repo: EmploymentStatusRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_list_returns_created(repo: EmploymentStatusRepository):
    await repo.create(code="ACTIVE", name="Active")
    await repo.create(code="TERMINATED", name="Terminated")

    items = await repo.list()

    assert {"Active", "Terminated"}.issubset({item.name for item in items})


async def test_update_existing(repo: EmploymentStatusRepository):
    employment_status = await repo.create(code="ACTIVE", name="Before")

    updated = await repo.update(employment_status.id, name="After")

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(repo: EmploymentStatusRepository):
    assert await repo.update(uuid.uuid4(), name="After") is None


async def test_delete_existing(repo: EmploymentStatusRepository):
    employment_status = await repo.create(code="ACTIVE", name="To Delete")

    deleted = await repo.delete(employment_status.id)

    assert deleted is True
    assert await repo.get(employment_status.id) is None


async def test_delete_missing_returns_false(repo: EmploymentStatusRepository):
    assert await repo.delete(uuid.uuid4()) is False


async def test_get_by_code(repo: EmploymentStatusRepository):
    employment_status = await repo.create(code="ACTIVE", name="Active")

    found = await repo.get_by_code("ACTIVE")

    assert found is not None
    assert found.id == employment_status.id
    assert await repo.get_by_code("missing") is None


async def test_paginate_returns_total_and_page_slice(repo: EmploymentStatusRepository):
    for i in range(5):
        await repo.create(code=f"S{i}", name=f"Status {i}")

    page = await repo.paginate(offset=1, limit=2)

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_paginate_defaults(repo: EmploymentStatusRepository):
    for i in range(3):
        await repo.create(code=f"S{i}", name=f"Status {i}")

    page = await repo.paginate()

    assert page.offset == 0
    assert page.limit == 50
    assert page.total == 3
    assert len(page.items) == 3


async def test_paginate_search_returns_matching_rows_by_name(repo: EmploymentStatusRepository):
    await repo.create(code="ACTIVE", name="Active")
    await repo.create(code="TERMINATED", name="Terminated")

    page = await repo.paginate(search=SearchParams(q="active"))

    assert page.total == 1
    assert page.items[0].name == "Active"


async def test_paginate_search_returns_matching_rows_by_code(repo: EmploymentStatusRepository):
    await repo.create(code="ON-LEAVE", name="On Leave")
    await repo.create(code="SUSPENDED", name="Suspended")

    page = await repo.paginate(search=SearchParams(q="leave"))

    assert page.total == 1
    assert page.items[0].code == "ON-LEAVE"


async def test_paginate_no_search_returns_all_rows(repo: EmploymentStatusRepository):
    await repo.create(code="ACTIVE", name="Active")
    await repo.create(code="TERMINATED", name="Terminated")

    page = await repo.paginate(search=None)

    assert page.total == 2
