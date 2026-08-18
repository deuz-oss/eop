import uuid
from collections.abc import AsyncGenerator
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.core.payroll import PayrollRunStatus
from eop_api.db.base import Base
from eop_api.repositories.payroll_run import PayrollRunRepository
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
def repo(session: AsyncSession) -> PayrollRunRepository:
    return PayrollRunRepository(session)


async def test_create_and_get(repo: PayrollRunRepository):
    payroll_run = await repo.create(code="RUN-001", name="First Run")

    fetched = await repo.get(payroll_run.id)

    assert fetched is not None
    assert fetched.code == "RUN-001"
    assert fetched.name == "First Run"


async def test_get_missing_returns_none(repo: PayrollRunRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_list_returns_created(repo: PayrollRunRepository):
    await repo.create(code="RUN-001", name="First Run")
    await repo.create(code="RUN-002", name="Second Run")

    items = await repo.list()

    assert {"First Run", "Second Run"}.issubset({item.name for item in items})


async def test_update_existing(repo: PayrollRunRepository):
    payroll_run = await repo.create(code="RUN-001", name="Before")

    updated = await repo.update(payroll_run.id, name="After")

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(repo: PayrollRunRepository):
    assert await repo.update(uuid.uuid4(), name="After") is None


async def test_delete_existing(repo: PayrollRunRepository):
    payroll_run = await repo.create(code="RUN-001", name="To Delete")

    deleted = await repo.delete(payroll_run.id)

    assert deleted is True
    assert await repo.get(payroll_run.id) is None


async def test_find_covering_date_returns_matching_period(repo: PayrollRunRepository):
    """Persistence-only: returns every raw match, any `status` -- interpreting
    `status` (AttendanceEvent Integrity workstream's lock rule) is the
    caller's job, not this repository's."""
    payroll_run = await repo.create(
        code="RUN-COVER",
        name="January",
        status=PayrollRunStatus.PROCESSING,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        currency="USD",
    )

    matches = await repo.find_covering_date(date(2026, 1, 15))

    assert {m.id for m in matches} == {payroll_run.id}


async def test_find_covering_date_excludes_non_matching_period(repo: PayrollRunRepository):
    await repo.create(
        code="RUN-FEB",
        name="February",
        status=PayrollRunStatus.PROCESSING,
        period_start=date(2026, 2, 1),
        period_end=date(2026, 2, 28),
        currency="USD",
    )

    matches = await repo.find_covering_date(date(2026, 1, 15))

    assert matches == []


async def test_find_covering_date_excludes_rows_with_null_period(repo: PayrollRunRepository):
    """A `PayrollRun` with `period_start`/`period_end` still `NULL` (the
    pre-Iteration-2 historical gap) never matches any date."""
    await repo.create(code="RUN-LEGACY", name="Legacy")

    matches = await repo.find_covering_date(date(2026, 1, 15))

    assert matches == []


async def test_delete_missing_returns_false(repo: PayrollRunRepository):
    assert await repo.delete(uuid.uuid4()) is False


async def test_get_by_code(repo: PayrollRunRepository):
    payroll_run = await repo.create(code="RUN-001", name="First Run")

    found = await repo.get_by_code("RUN-001")

    assert found is not None
    assert found.id == payroll_run.id
    assert await repo.get_by_code("missing") is None


async def test_paginate_returns_total_and_page_slice(repo: PayrollRunRepository):
    for i in range(5):
        await repo.create(code=f"RUN-{i}", name=f"Run {i}")

    page = await repo.paginate(offset=1, limit=2)

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_paginate_defaults(repo: PayrollRunRepository):
    for i in range(3):
        await repo.create(code=f"RUN-{i}", name=f"Run {i}")

    page = await repo.paginate()

    assert page.offset == 0
    assert page.limit == 50
    assert page.total == 3
    assert len(page.items) == 3


async def test_paginate_search_returns_matching_rows_by_name(repo: PayrollRunRepository):
    await repo.create(code="RUN-001", name="August Run")
    await repo.create(code="RUN-002", name="September Run")

    page = await repo.paginate(search=SearchParams(q="august"))

    assert page.total == 1
    assert page.items[0].name == "August Run"


async def test_paginate_search_returns_matching_rows_by_code(repo: PayrollRunRepository):
    await repo.create(code="RUN-AUG-01", name="First")
    await repo.create(code="RUN-SEP-01", name="Second")

    page = await repo.paginate(search=SearchParams(q="aug"))

    assert page.total == 1
    assert page.items[0].code == "RUN-AUG-01"


async def test_paginate_no_search_returns_all_rows(repo: PayrollRunRepository):
    await repo.create(code="RUN-001", name="First Run")
    await repo.create(code="RUN-002", name="Second Run")

    page = await repo.paginate(search=None)

    assert page.total == 2
