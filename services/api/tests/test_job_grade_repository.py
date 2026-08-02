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
from eop_api.repositories.job_grade import JobGradeRepository
from eop_api.schemas.search import FilterParams, SearchParams

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
def repo(session: AsyncSession) -> JobGradeRepository:
    return JobGradeRepository(session)


async def test_create_and_get(repo: JobGradeRepository):
    job_grade = await repo.create(code="L1", name="Junior", level=1)

    fetched = await repo.get(job_grade.id)

    assert fetched is not None
    assert fetched.code == "L1"
    assert fetched.name == "Junior"
    assert fetched.level == 1
    assert fetched.description is None


async def test_get_missing_returns_none(repo: JobGradeRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_list_returns_created(repo: JobGradeRepository):
    await repo.create(code="L1", name="Junior", level=1)
    await repo.create(code="L2", name="Mid", level=2)

    items = await repo.list()

    assert {"Junior", "Mid"}.issubset({item.name for item in items})


async def test_update_existing(repo: JobGradeRepository):
    job_grade = await repo.create(code="L1", name="Before", level=1)

    updated = await repo.update(job_grade.id, name="After")

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(repo: JobGradeRepository):
    assert await repo.update(uuid.uuid4(), name="After") is None


async def test_delete_existing(repo: JobGradeRepository):
    job_grade = await repo.create(code="L1", name="To Delete", level=1)

    deleted = await repo.delete(job_grade.id)

    assert deleted is True
    assert await repo.get(job_grade.id) is None


async def test_delete_missing_returns_false(repo: JobGradeRepository):
    assert await repo.delete(uuid.uuid4()) is False


async def test_get_by_code(repo: JobGradeRepository):
    job_grade = await repo.create(code="L1", name="Junior", level=1)

    found = await repo.get_by_code("L1")

    assert found is not None
    assert found.id == job_grade.id
    assert await repo.get_by_code("missing") is None


async def test_get_by_level(repo: JobGradeRepository):
    job_grade = await repo.create(code="L1", name="Junior", level=1)

    found = await repo.get_by_level(1)

    assert found is not None
    assert found.id == job_grade.id
    assert await repo.get_by_level(99) is None


async def test_paginate_returns_total_and_page_slice(repo: JobGradeRepository):
    for i in range(5):
        await repo.create(code=f"L{i}", name=f"Grade {i}", level=i)

    page = await repo.paginate(offset=1, limit=2)

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_paginate_defaults(repo: JobGradeRepository):
    for i in range(3):
        await repo.create(code=f"L{i}", name=f"Grade {i}", level=i)

    page = await repo.paginate()

    assert page.offset == 0
    assert page.limit == 50
    assert page.total == 3
    assert len(page.items) == 3


async def test_paginate_search_returns_matching_rows_by_name(repo: JobGradeRepository):
    await repo.create(code="L1", name="Junior Engineer", level=1)
    await repo.create(code="L2", name="Senior Manager", level=2)

    page = await repo.paginate(search=SearchParams(q="junior"))

    assert page.total == 1
    assert page.items[0].name == "Junior Engineer"


async def test_paginate_search_returns_matching_rows_by_code(repo: JobGradeRepository):
    await repo.create(code="ENG-L1", name="Junior", level=1)
    await repo.create(code="MGR-L2", name="Senior", level=2)

    page = await repo.paginate(search=SearchParams(q="eng"))

    assert page.total == 1
    assert page.items[0].code == "ENG-L1"


async def test_paginate_no_search_returns_all_rows(repo: JobGradeRepository):
    await repo.create(code="L1", name="Junior", level=1)
    await repo.create(code="L2", name="Senior", level=2)

    page = await repo.paginate(search=None)

    assert page.total == 2


async def test_paginate_filters_by_level(repo: JobGradeRepository):
    job_grade = await repo.create(code="L1", name="Junior", level=1)
    await repo.create(code="L2", name="Senior", level=2)

    page = await repo.paginate(filters=FilterParams(values={"level": 1}))

    assert page.total == 1
    assert page.items[0].id == job_grade.id


async def test_paginate_without_filters_returns_all_rows(repo: JobGradeRepository):
    await repo.create(code="L1", name="Junior", level=1)
    await repo.create(code="L2", name="Senior", level=2)

    page = await repo.paginate()

    assert page.total == 2
