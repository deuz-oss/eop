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
from eop_api.repositories.store_type import StoreTypeRepository
from eop_api.schemas.search import SearchParams

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def connection() -> AsyncGenerator[AsyncConnection]:
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
def repo(session: AsyncSession) -> StoreTypeRepository:
    return StoreTypeRepository(session)


async def test_create_and_get(repo: StoreTypeRepository):
    store_type = await repo.create(code="MT", name="Modern Trade", description="Modern trade")

    fetched = await repo.get(store_type.id)

    assert fetched is not None
    assert fetched.code == "MT"
    assert fetched.name == "Modern Trade"
    assert fetched.description == "Modern trade"


async def test_get_missing_returns_none(repo: StoreTypeRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_get_by_code(repo: StoreTypeRepository):
    store_type = await repo.create(code="GT", name="General Trade")

    found = await repo.get_by_code("GT")

    assert found is not None
    assert found.id == store_type.id
    assert await repo.get_by_code("missing") is None


async def test_list_returns_created(repo: StoreTypeRepository):
    await repo.create(code="MT", name="Modern Trade")
    await repo.create(code="GT", name="General Trade")

    items = await repo.list()

    assert {"Modern Trade", "General Trade"}.issubset({item.name for item in items})


async def test_update_existing(repo: StoreTypeRepository):
    store_type = await repo.create(code="MT", name="Before")

    updated = await repo.update(store_type.id, name="After")

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(repo: StoreTypeRepository):
    assert await repo.update(uuid.uuid4(), name="After") is None


async def test_delete_existing(repo: StoreTypeRepository):
    store_type = await repo.create(code="MT", name="Modern Trade")

    deleted = await repo.delete(store_type.id)

    assert deleted is True
    assert await repo.get(store_type.id) is None


async def test_delete_missing_returns_false(repo: StoreTypeRepository):
    assert await repo.delete(uuid.uuid4()) is False


async def test_paginate_search_returns_matching_rows(repo: StoreTypeRepository):
    await repo.create(code="MT", name="Modern Trade")
    await repo.create(code="GT", name="General Trade")

    page = await repo.paginate(search=SearchParams(q="modern"))

    assert page.total == 1
    assert page.items[0].name == "Modern Trade"


async def test_paginate_no_search_returns_all_rows(repo: StoreTypeRepository):
    await repo.create(code="MT", name="Modern Trade")
    await repo.create(code="GT", name="General Trade")

    page = await repo.paginate(search=None)

    assert page.total == 2
