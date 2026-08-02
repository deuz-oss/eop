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
from eop_api.repositories.employment_type import EmploymentTypeRepository
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
def repo(session: AsyncSession) -> EmploymentTypeRepository:
    return EmploymentTypeRepository(session)


async def test_create_and_get(repo: EmploymentTypeRepository):
    employment_type = await repo.create(code="FT", name="Full-Time")

    fetched = await repo.get(employment_type.id)

    assert fetched is not None
    assert fetched.code == "FT"
    assert fetched.name == "Full-Time"
    assert fetched.description is None


async def test_get_missing_returns_none(repo: EmploymentTypeRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_list_returns_created(repo: EmploymentTypeRepository):
    await repo.create(code="FT", name="Full-Time")
    await repo.create(code="PT", name="Part-Time")

    items = await repo.list()

    assert {"Full-Time", "Part-Time"}.issubset({item.name for item in items})


async def test_update_existing(repo: EmploymentTypeRepository):
    employment_type = await repo.create(code="FT", name="Before")

    updated = await repo.update(employment_type.id, name="After")

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(repo: EmploymentTypeRepository):
    assert await repo.update(uuid.uuid4(), name="After") is None


async def test_delete_existing(repo: EmploymentTypeRepository):
    employment_type = await repo.create(code="FT", name="To Delete")

    deleted = await repo.delete(employment_type.id)

    assert deleted is True
    assert await repo.get(employment_type.id) is None


async def test_delete_missing_returns_false(repo: EmploymentTypeRepository):
    assert await repo.delete(uuid.uuid4()) is False


async def test_get_by_code(repo: EmploymentTypeRepository):
    employment_type = await repo.create(code="FT", name="Full-Time")

    found = await repo.get_by_code("FT")

    assert found is not None
    assert found.id == employment_type.id
    assert await repo.get_by_code("missing") is None


async def test_paginate_returns_total_and_page_slice(repo: EmploymentTypeRepository):
    for i in range(5):
        await repo.create(code=f"T{i}", name=f"Type {i}")

    page = await repo.paginate(offset=1, limit=2)

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_paginate_defaults(repo: EmploymentTypeRepository):
    for i in range(3):
        await repo.create(code=f"T{i}", name=f"Type {i}")

    page = await repo.paginate()

    assert page.offset == 0
    assert page.limit == 50
    assert page.total == 3
    assert len(page.items) == 3


async def test_paginate_search_returns_matching_rows_by_name(repo: EmploymentTypeRepository):
    await repo.create(code="FT", name="Full-Time")
    await repo.create(code="PT", name="Part-Time")

    page = await repo.paginate(search=SearchParams(q="full"))

    assert page.total == 1
    assert page.items[0].name == "Full-Time"


async def test_paginate_search_returns_matching_rows_by_code(repo: EmploymentTypeRepository):
    await repo.create(code="CONTRACT-01", name="Contractor")
    await repo.create(code="PERM-01", name="Permanent")

    page = await repo.paginate(search=SearchParams(q="contract"))

    assert page.total == 1
    assert page.items[0].code == "CONTRACT-01"


async def test_paginate_no_search_returns_all_rows(repo: EmploymentTypeRepository):
    await repo.create(code="FT", name="Full-Time")
    await repo.create(code="PT", name="Part-Time")

    page = await repo.paginate(search=None)

    assert page.total == 2
