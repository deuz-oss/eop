import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.schemas.holiday import HolidayCreate, HolidayUpdate
from eop_api.schemas.pagination import PaginationParams
from eop_api.schemas.search import SearchParams
from eop_api.services.holiday import (
    DuplicateHolidayCodeError,
    DuplicateHolidayDateError,
    HolidayService,
)
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session_factory() -> AsyncGenerator[Callable[[], AsyncSession]]:
    """A session factory backed by the real (migration-managed) `holidays` table.

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
            await conn.execute(text("TRUNCATE TABLE holidays CASCADE"))
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> HolidayService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return HolidayService(uow_factory)


def _create(code: str = "NEWYEAR", name: str = "New Year's Day", **overrides) -> HolidayCreate:
    values = {"code": code, "name": name, "holiday_date": date(2027, 1, 1)}
    values.update(overrides)
    return HolidayCreate(**values)


async def test_create_and_get(service: HolidayService):
    holiday = await service.create(_create())

    fetched = await service.get(holiday.id)

    assert fetched is not None
    assert fetched.code == "NEWYEAR"
    assert fetched.name == "New Year's Day"
    assert fetched.holiday_date == date(2027, 1, 1)


async def test_create_rejects_duplicate_code(service: HolidayService):
    await service.create(_create(code="NEWYEAR", holiday_date=date(2027, 1, 1)))

    with pytest.raises(DuplicateHolidayCodeError):
        await service.create(_create(code="NEWYEAR", name="Other", holiday_date=date(2027, 12, 25)))


async def test_create_rejects_duplicate_holiday_date(service: HolidayService):
    await service.create(_create(code="NEWYEAR", holiday_date=date(2027, 1, 1)))

    with pytest.raises(DuplicateHolidayDateError):
        await service.create(_create(code="OTHER", name="Other", holiday_date=date(2027, 1, 1)))


async def test_get_missing_returns_none(service: HolidayService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(service: HolidayService):
    await service.create(_create(code="NEWYEAR", name="New Year's Day"))
    await service.create(
        _create(code="INDEP", name="Independence Day", holiday_date=date(2027, 8, 17))
    )

    items = await service.list()

    assert {"New Year's Day", "Independence Day"}.issubset({item.name for item in items})


async def test_update_existing(service: HolidayService):
    holiday = await service.create(_create(name="Before"))

    updated = await service.update(holiday.id, HolidayUpdate(name="After"))

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(service: HolidayService):
    assert await service.update(uuid.uuid4(), HolidayUpdate(name="After")) is None


async def test_update_rejects_duplicate_code(service: HolidayService):
    await service.create(_create(code="NEWYEAR", name="New Year's Day"))
    other = await service.create(
        _create(code="INDEP", name="Independence Day", holiday_date=date(2027, 8, 17))
    )

    with pytest.raises(DuplicateHolidayCodeError):
        await service.update(other.id, HolidayUpdate(code="NEWYEAR"))


async def test_update_allows_unchanged_code(service: HolidayService):
    holiday = await service.create(_create(code="NEWYEAR", name="New Year's Day"))

    updated = await service.update(
        holiday.id, HolidayUpdate(code="NEWYEAR", name="New Year's Day Renamed")
    )

    assert updated is not None
    assert updated.name == "New Year's Day Renamed"


async def test_update_rejects_duplicate_holiday_date(service: HolidayService):
    await service.create(_create(code="NEWYEAR", holiday_date=date(2027, 1, 1)))
    other = await service.create(
        _create(code="INDEP", name="Independence Day", holiday_date=date(2027, 8, 17))
    )

    with pytest.raises(DuplicateHolidayDateError):
        await service.update(other.id, HolidayUpdate(holiday_date=date(2027, 1, 1)))


async def test_update_allows_unchanged_holiday_date(service: HolidayService):
    holiday = await service.create(_create(code="NEWYEAR", holiday_date=date(2027, 1, 1)))

    updated = await service.update(
        holiday.id, HolidayUpdate(holiday_date=date(2027, 1, 1), name="Renamed")
    )

    assert updated is not None
    assert updated.name == "Renamed"


async def test_delete_existing(service: HolidayService):
    holiday = await service.create(_create(name="To Delete"))

    deleted = await service.delete(holiday.id)

    assert deleted is True
    assert await service.get(holiday.id) is None


async def test_delete_missing_returns_false(service: HolidayService):
    assert await service.delete(uuid.uuid4()) is False


async def test_list_paginated_passes_through_offset_and_limit(service: HolidayService):
    for i in range(5):
        await service.create(
            _create(code=f"H{i}", name=f"Holiday {i}", holiday_date=date(2027, 1, i + 1))
        )

    page = await service.list_paginated(PaginationParams(offset=1, limit=2))

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_list_paginated_passes_through_search(service: HolidayService):
    await service.create(_create(code="NEWYEAR", name="New Year's Day"))
    await service.create(
        _create(code="INDEP", name="Independence Day", holiday_date=date(2027, 8, 17))
    )

    page = await service.list_paginated(
        PaginationParams(offset=0, limit=50), SearchParams(q="new year")
    )

    assert page.total == 1
    assert page.items[0].name == "New Year's Day"
