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
from eop_api.db.base import Base
from eop_api.repositories.holiday import HolidayRepository
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
def repo(session: AsyncSession) -> HolidayRepository:
    return HolidayRepository(session)


async def test_create_and_get(repo: HolidayRepository):
    holiday = await repo.create(
        code="NEWYEAR", name="New Year's Day", holiday_date=date(2027, 1, 1)
    )

    fetched = await repo.get(holiday.id)

    assert fetched is not None
    assert fetched.code == "NEWYEAR"
    assert fetched.name == "New Year's Day"
    assert fetched.description is None
    assert fetched.holiday_date == date(2027, 1, 1)


async def test_get_missing_returns_none(repo: HolidayRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_list_returns_created(repo: HolidayRepository):
    await repo.create(code="NEWYEAR", name="New Year's Day", holiday_date=date(2027, 1, 1))
    await repo.create(code="INDEP", name="Independence Day", holiday_date=date(2027, 8, 17))

    items = await repo.list()

    assert {"New Year's Day", "Independence Day"}.issubset({item.name for item in items})


async def test_update_existing(repo: HolidayRepository):
    holiday = await repo.create(code="NEWYEAR", name="Before", holiday_date=date(2027, 1, 1))

    updated = await repo.update(holiday.id, name="After")

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(repo: HolidayRepository):
    assert await repo.update(uuid.uuid4(), name="After") is None


async def test_delete_existing(repo: HolidayRepository):
    holiday = await repo.create(code="NEWYEAR", name="To Delete", holiday_date=date(2027, 1, 1))

    deleted = await repo.delete(holiday.id)

    assert deleted is True
    assert await repo.get(holiday.id) is None


async def test_delete_missing_returns_false(repo: HolidayRepository):
    assert await repo.delete(uuid.uuid4()) is False


async def test_get_by_code(repo: HolidayRepository):
    holiday = await repo.create(
        code="NEWYEAR", name="New Year's Day", holiday_date=date(2027, 1, 1)
    )

    found = await repo.get_by_code("NEWYEAR")

    assert found is not None
    assert found.id == holiday.id
    assert await repo.get_by_code("missing") is None


async def test_get_by_holiday_date(repo: HolidayRepository):
    holiday = await repo.create(
        code="NEWYEAR", name="New Year's Day", holiday_date=date(2027, 1, 1)
    )

    found = await repo.get_by_holiday_date(date(2027, 1, 1))

    assert found is not None
    assert found.id == holiday.id
    assert await repo.get_by_holiday_date(date(2027, 12, 25)) is None


async def test_paginate_returns_total_and_page_slice(repo: HolidayRepository):
    for i in range(5):
        await repo.create(code=f"H{i}", name=f"Holiday {i}", holiday_date=date(2027, 1, i + 1))

    page = await repo.paginate(offset=1, limit=2)

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_paginate_defaults(repo: HolidayRepository):
    for i in range(3):
        await repo.create(code=f"H{i}", name=f"Holiday {i}", holiday_date=date(2027, 1, i + 1))

    page = await repo.paginate()

    assert page.offset == 0
    assert page.limit == 50
    assert page.total == 3
    assert len(page.items) == 3


async def test_paginate_search_returns_matching_rows_by_name(repo: HolidayRepository):
    await repo.create(code="NEWYEAR", name="New Year's Day", holiday_date=date(2027, 1, 1))
    await repo.create(code="INDEP", name="Independence Day", holiday_date=date(2027, 8, 17))

    page = await repo.paginate(search=SearchParams(q="new year"))

    assert page.total == 1
    assert page.items[0].name == "New Year's Day"


async def test_paginate_search_returns_matching_rows_by_code(repo: HolidayRepository):
    await repo.create(code="NEWYEAR-01", name="Early", holiday_date=date(2027, 1, 1))
    await repo.create(code="INDEP-01", name="Late", holiday_date=date(2027, 8, 17))

    page = await repo.paginate(search=SearchParams(q="newyear"))

    assert page.total == 1
    assert page.items[0].code == "NEWYEAR-01"


async def test_paginate_no_search_returns_all_rows(repo: HolidayRepository):
    await repo.create(code="NEWYEAR", name="New Year's Day", holiday_date=date(2027, 1, 1))
    await repo.create(code="INDEP", name="Independence Day", holiday_date=date(2027, 8, 17))

    page = await repo.paginate(search=None)

    assert page.total == 2


async def test_paginate_filters_by_holiday_date(repo: HolidayRepository):
    await repo.create(code="NEWYEAR", name="New Year's Day", holiday_date=date(2027, 1, 1))
    await repo.create(code="INDEP", name="Independence Day", holiday_date=date(2027, 8, 17))

    page = await repo.paginate(filters=FilterParams(values={"holiday_date": date(2027, 1, 1)}))

    assert page.total == 1
    assert page.items[0].code == "NEWYEAR"
