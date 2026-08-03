import uuid
from collections.abc import AsyncGenerator
from datetime import time

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
from eop_api.repositories.shift import ShiftRepository
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
def repo(session: AsyncSession) -> ShiftRepository:
    return ShiftRepository(session)


async def test_create_and_get(repo: ShiftRepository):
    shift = await repo.create(
        code="MORNING", name="Morning Shift", start_time=time(9, 0), end_time=time(17, 0)
    )

    fetched = await repo.get(shift.id)

    assert fetched is not None
    assert fetched.code == "MORNING"
    assert fetched.name == "Morning Shift"
    assert fetched.description is None
    assert fetched.start_time == time(9, 0)
    assert fetched.end_time == time(17, 0)
    assert fetched.break_duration_minutes == 0
    assert fetched.grace_period_minutes == 0


async def test_get_missing_returns_none(repo: ShiftRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_list_returns_created(repo: ShiftRepository):
    await repo.create(
        code="MORNING", name="Morning Shift", start_time=time(9, 0), end_time=time(17, 0)
    )
    await repo.create(
        code="NIGHT", name="Night Shift", start_time=time(22, 0), end_time=time(6, 0)
    )

    items = await repo.list()

    assert {"Morning Shift", "Night Shift"}.issubset({item.name for item in items})


async def test_update_existing(repo: ShiftRepository):
    shift = await repo.create(
        code="MORNING", name="Before", start_time=time(9, 0), end_time=time(17, 0)
    )

    updated = await repo.update(shift.id, name="After")

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(repo: ShiftRepository):
    assert await repo.update(uuid.uuid4(), name="After") is None


async def test_delete_existing(repo: ShiftRepository):
    shift = await repo.create(
        code="MORNING", name="To Delete", start_time=time(9, 0), end_time=time(17, 0)
    )

    deleted = await repo.delete(shift.id)

    assert deleted is True
    assert await repo.get(shift.id) is None


async def test_delete_missing_returns_false(repo: ShiftRepository):
    assert await repo.delete(uuid.uuid4()) is False


async def test_get_by_code(repo: ShiftRepository):
    shift = await repo.create(
        code="MORNING", name="Morning Shift", start_time=time(9, 0), end_time=time(17, 0)
    )

    found = await repo.get_by_code("MORNING")

    assert found is not None
    assert found.id == shift.id
    assert await repo.get_by_code("missing") is None


async def test_paginate_returns_total_and_page_slice(repo: ShiftRepository):
    for i in range(5):
        await repo.create(
            code=f"S{i}", name=f"Shift {i}", start_time=time(9, 0), end_time=time(17, 0)
        )

    page = await repo.paginate(offset=1, limit=2)

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_paginate_defaults(repo: ShiftRepository):
    for i in range(3):
        await repo.create(
            code=f"S{i}", name=f"Shift {i}", start_time=time(9, 0), end_time=time(17, 0)
        )

    page = await repo.paginate()

    assert page.offset == 0
    assert page.limit == 50
    assert page.total == 3
    assert len(page.items) == 3


async def test_paginate_search_returns_matching_rows_by_name(repo: ShiftRepository):
    await repo.create(
        code="MORNING", name="Morning Shift", start_time=time(9, 0), end_time=time(17, 0)
    )
    await repo.create(
        code="NIGHT", name="Night Shift", start_time=time(22, 0), end_time=time(6, 0)
    )

    page = await repo.paginate(search=SearchParams(q="morning"))

    assert page.total == 1
    assert page.items[0].name == "Morning Shift"


async def test_paginate_search_returns_matching_rows_by_code(repo: ShiftRepository):
    await repo.create(
        code="MORNING-01", name="Early", start_time=time(9, 0), end_time=time(17, 0)
    )
    await repo.create(code="NIGHT-01", name="Late", start_time=time(22, 0), end_time=time(6, 0))

    page = await repo.paginate(search=SearchParams(q="morning"))

    assert page.total == 1
    assert page.items[0].code == "MORNING-01"


async def test_paginate_no_search_returns_all_rows(repo: ShiftRepository):
    await repo.create(
        code="MORNING", name="Morning Shift", start_time=time(9, 0), end_time=time(17, 0)
    )
    await repo.create(
        code="NIGHT", name="Night Shift", start_time=time(22, 0), end_time=time(6, 0)
    )

    page = await repo.paginate(search=None)

    assert page.total == 2
