import uuid
from collections.abc import AsyncGenerator, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.schemas.employment_status import EmploymentStatusCreate, EmploymentStatusUpdate
from eop_api.schemas.pagination import PaginationParams
from eop_api.schemas.search import SearchParams
from eop_api.services.employment_status import (
    DuplicateEmploymentStatusCodeError,
    EmploymentStatusService,
)
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session_factory() -> AsyncGenerator[Callable[[], AsyncSession]]:
    """A session factory backed by the real (migration-managed) `employment_statuses` table.

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
            await conn.execute(text("TRUNCATE TABLE employment_statuses CASCADE"))
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> EmploymentStatusService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return EmploymentStatusService(uow_factory)


async def test_create_and_get(service: EmploymentStatusService):
    employment_status = await service.create(EmploymentStatusCreate(code="ACTIVE", name="Active"))

    fetched = await service.get(employment_status.id)

    assert fetched is not None
    assert fetched.code == "ACTIVE"
    assert fetched.name == "Active"


async def test_create_rejects_duplicate_code(service: EmploymentStatusService):
    await service.create(EmploymentStatusCreate(code="ACTIVE", name="Active"))

    with pytest.raises(DuplicateEmploymentStatusCodeError):
        await service.create(EmploymentStatusCreate(code="ACTIVE", name="Active Two"))


async def test_get_missing_returns_none(service: EmploymentStatusService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(service: EmploymentStatusService):
    await service.create(EmploymentStatusCreate(code="ACTIVE", name="Active"))
    await service.create(EmploymentStatusCreate(code="TERMINATED", name="Terminated"))

    items = await service.list()

    assert {"Active", "Terminated"}.issubset({item.name for item in items})


async def test_update_existing(service: EmploymentStatusService):
    employment_status = await service.create(EmploymentStatusCreate(code="ACTIVE", name="Before"))

    updated = await service.update(employment_status.id, EmploymentStatusUpdate(name="After"))

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(service: EmploymentStatusService):
    assert await service.update(uuid.uuid4(), EmploymentStatusUpdate(name="After")) is None


async def test_update_rejects_duplicate_code(service: EmploymentStatusService):
    await service.create(EmploymentStatusCreate(code="ACTIVE", name="Active"))
    other = await service.create(EmploymentStatusCreate(code="TERMINATED", name="Terminated"))

    with pytest.raises(DuplicateEmploymentStatusCodeError):
        await service.update(other.id, EmploymentStatusUpdate(code="ACTIVE"))


async def test_update_allows_unchanged_code(service: EmploymentStatusService):
    employment_status = await service.create(EmploymentStatusCreate(code="ACTIVE", name="Active"))

    updated = await service.update(
        employment_status.id, EmploymentStatusUpdate(code="ACTIVE", name="Active Renamed")
    )

    assert updated is not None
    assert updated.name == "Active Renamed"


async def test_delete_existing(service: EmploymentStatusService):
    employment_status = await service.create(
        EmploymentStatusCreate(code="ACTIVE", name="To Delete")
    )

    deleted = await service.delete(employment_status.id)

    assert deleted is True
    assert await service.get(employment_status.id) is None


async def test_delete_missing_returns_false(service: EmploymentStatusService):
    assert await service.delete(uuid.uuid4()) is False


async def test_list_paginated_passes_through_offset_and_limit(service: EmploymentStatusService):
    for i in range(5):
        await service.create(EmploymentStatusCreate(code=f"S{i}", name=f"Status {i}"))

    page = await service.list_paginated(PaginationParams(offset=1, limit=2))

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_list_paginated_passes_through_search(service: EmploymentStatusService):
    await service.create(EmploymentStatusCreate(code="ACTIVE", name="Active"))
    await service.create(EmploymentStatusCreate(code="TERMINATED", name="Terminated"))

    page = await service.list_paginated(
        PaginationParams(offset=0, limit=50), SearchParams(q="active")
    )

    assert page.total == 1
    assert page.items[0].name == "Active"
