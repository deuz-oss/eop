import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import time

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.schemas.pagination import PaginationParams
from eop_api.schemas.search import SearchParams
from eop_api.schemas.shift import ShiftCreate, ShiftUpdate
from eop_api.services.shift import (
    DuplicateShiftCodeError,
    InvalidBreakDurationError,
    InvalidShiftTimeError,
    ShiftService,
)
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session_factory() -> AsyncGenerator[Callable[[], AsyncSession]]:
    """A session factory backed by the real (migration-managed) `shifts` table.

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
            await conn.execute(text("TRUNCATE TABLE shifts CASCADE"))
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> ShiftService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return ShiftService(uow_factory)


def _create(code: str = "MORNING", name: str = "Morning Shift", **overrides) -> ShiftCreate:
    values = {"code": code, "name": name, "start_time": time(9, 0), "end_time": time(17, 0)}
    values.update(overrides)
    return ShiftCreate(**values)


async def test_create_and_get(service: ShiftService):
    shift = await service.create(_create())

    fetched = await service.get(shift.id)

    assert fetched is not None
    assert fetched.code == "MORNING"
    assert fetched.name == "Morning Shift"
    assert fetched.start_time == time(9, 0)
    assert fetched.end_time == time(17, 0)


async def test_create_rejects_duplicate_code(service: ShiftService):
    await service.create(_create(code="MORNING"))

    with pytest.raises(DuplicateShiftCodeError):
        await service.create(_create(code="MORNING", name="Morning Shift Two"))


async def test_create_rejects_equal_start_and_end_time(service: ShiftService):
    with pytest.raises(InvalidShiftTimeError):
        await service.create(_create(start_time=time(9, 0), end_time=time(9, 0)))


async def test_create_allows_overnight_shift(service: ShiftService):
    shift = await service.create(_create(start_time=time(22, 0), end_time=time(6, 0)))

    assert shift.start_time == time(22, 0)
    assert shift.end_time == time(6, 0)


async def test_create_rejects_negative_break_duration(service: ShiftService):
    with pytest.raises(InvalidBreakDurationError):
        await service.create(_create(break_duration_minutes=-1))


async def test_get_missing_returns_none(service: ShiftService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(service: ShiftService):
    await service.create(_create(code="MORNING", name="Morning Shift"))
    await service.create(
        _create(code="NIGHT", name="Night Shift", start_time=time(22, 0), end_time=time(6, 0))
    )

    items = await service.list()

    assert {"Morning Shift", "Night Shift"}.issubset({item.name for item in items})


async def test_update_existing(service: ShiftService):
    shift = await service.create(_create(name="Before"))

    updated = await service.update(shift.id, ShiftUpdate(name="After"))

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(service: ShiftService):
    assert await service.update(uuid.uuid4(), ShiftUpdate(name="After")) is None


async def test_update_rejects_duplicate_code(service: ShiftService):
    await service.create(_create(code="MORNING", name="Morning Shift"))
    other = await service.create(
        _create(code="NIGHT", name="Night Shift", start_time=time(22, 0), end_time=time(6, 0))
    )

    with pytest.raises(DuplicateShiftCodeError):
        await service.update(other.id, ShiftUpdate(code="MORNING"))


async def test_update_allows_unchanged_code(service: ShiftService):
    shift = await service.create(_create(code="MORNING", name="Morning Shift"))

    updated = await service.update(
        shift.id, ShiftUpdate(code="MORNING", name="Morning Shift Renamed")
    )

    assert updated is not None
    assert updated.name == "Morning Shift Renamed"


async def test_update_rejects_equal_start_and_end_time(service: ShiftService):
    shift = await service.create(_create(start_time=time(9, 0), end_time=time(17, 0)))

    with pytest.raises(InvalidShiftTimeError):
        await service.update(
            shift.id, ShiftUpdate(start_time=time(12, 0), end_time=time(12, 0))
        )


async def test_update_rejects_negative_break_duration(service: ShiftService):
    shift = await service.create(_create())

    with pytest.raises(InvalidBreakDurationError):
        await service.update(shift.id, ShiftUpdate(break_duration_minutes=-5))


async def test_update_partial_payload_validated_against_effective_end_time(
    service: ShiftService,
):
    """Only `start_time` is sent, but it collides with the persisted `end_time` --
    the effective-value merge must still catch it."""
    shift = await service.create(_create(start_time=time(9, 0), end_time=time(17, 0)))

    with pytest.raises(InvalidShiftTimeError):
        await service.update(shift.id, ShiftUpdate(start_time=time(17, 0)))


async def test_delete_existing(service: ShiftService):
    shift = await service.create(_create(name="To Delete"))

    deleted = await service.delete(shift.id)

    assert deleted is True
    assert await service.get(shift.id) is None


async def test_delete_missing_returns_false(service: ShiftService):
    assert await service.delete(uuid.uuid4()) is False


async def test_list_paginated_passes_through_offset_and_limit(service: ShiftService):
    for i in range(5):
        await service.create(_create(code=f"S{i}", name=f"Shift {i}"))

    page = await service.list_paginated(PaginationParams(offset=1, limit=2))

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_list_paginated_passes_through_search(service: ShiftService):
    await service.create(_create(code="MORNING", name="Morning Shift"))
    await service.create(
        _create(code="NIGHT", name="Night Shift", start_time=time(22, 0), end_time=time(6, 0))
    )

    page = await service.list_paginated(
        PaginationParams(offset=0, limit=50), SearchParams(q="morning")
    )

    assert page.total == 1
    assert page.items[0].name == "Morning Shift"
