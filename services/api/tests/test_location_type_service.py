import uuid
from collections.abc import AsyncGenerator, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.schemas.location_type import LocationTypeCreate, LocationTypeUpdate
from eop_api.schemas.pagination import PaginationParams
from eop_api.schemas.search import SearchParams
from eop_api.services.location_type import LocationTypeService
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session_factory() -> AsyncGenerator[Callable[[], AsyncSession]]:
    """A session factory backed by the real (migration-managed) `location_types` table.

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
            await conn.execute(text("TRUNCATE TABLE location_types CASCADE"))
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> LocationTypeService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return LocationTypeService(uow_factory)


async def test_create_and_get(service: LocationTypeService):
    location_type = await service.create(LocationTypeCreate(code="warehouse", name="Warehouse"))

    fetched = await service.get(location_type.id)

    assert fetched is not None
    assert fetched.code == "warehouse"
    assert fetched.name == "Warehouse"


async def test_get_missing_returns_none(service: LocationTypeService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(service: LocationTypeService):
    await service.create(LocationTypeCreate(code="warehouse", name="Warehouse"))
    await service.create(LocationTypeCreate(code="store", name="Store"))

    items = await service.list()

    assert {"Warehouse", "Store"}.issubset({item.name for item in items})


async def test_update_existing(service: LocationTypeService):
    location_type = await service.create(LocationTypeCreate(code="before", name="Before"))

    updated = await service.update(location_type.id, LocationTypeUpdate(name="After"))

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(service: LocationTypeService):
    assert await service.update(uuid.uuid4(), LocationTypeUpdate(name="After")) is None


async def test_delete_existing(service: LocationTypeService):
    location_type = await service.create(LocationTypeCreate(code="to-delete", name="To Delete"))

    deleted = await service.delete(location_type.id)

    assert deleted is True
    assert await service.get(location_type.id) is None


async def test_delete_missing_returns_false(service: LocationTypeService):
    assert await service.delete(uuid.uuid4()) is False


async def test_list_paginated_passes_through_offset_and_limit(service: LocationTypeService):
    for i in range(5):
        await service.create(LocationTypeCreate(code=f"type-{i}", name=f"Type {i}"))

    page = await service.list_paginated(PaginationParams(offset=1, limit=2))

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_list_paginated_passes_through_search(service: LocationTypeService):
    await service.create(LocationTypeCreate(code="warehouse", name="Warehouse"))
    await service.create(LocationTypeCreate(code="store", name="Store"))

    page = await service.list_paginated(
        PaginationParams(offset=0, limit=50), SearchParams(q="ware")
    )

    assert page.total == 1
    assert page.items[0].name == "Warehouse"
