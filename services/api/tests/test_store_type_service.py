import uuid
from collections.abc import AsyncGenerator, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.schemas.store_type import StoreTypeCreate, StoreTypeUpdate
from eop_api.services.store_type import DuplicateStoreTypeCodeError, StoreTypeService
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session_factory() -> AsyncGenerator[Callable[[], AsyncSession]]:
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory: Callable[[], AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)

    try:
        yield factory
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE store_types CASCADE"))
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> StoreTypeService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return StoreTypeService(uow_factory)


def _create(code: str = "MT", **overrides) -> StoreTypeCreate:
    values = {"code": code, "name": "Modern Trade"}
    values.update(overrides)
    return StoreTypeCreate(**values)


async def test_create_and_get(service: StoreTypeService):
    store_type = await service.create(_create())

    fetched = await service.get(store_type.id)

    assert fetched is not None
    assert fetched.code == "MT"
    assert fetched.name == "Modern Trade"


async def test_create_rejects_duplicate_code(service: StoreTypeService):
    await service.create(_create(code="MT"))

    with pytest.raises(DuplicateStoreTypeCodeError):
        await service.create(_create(code="MT", name="Other"))


async def test_get_missing_returns_none(service: StoreTypeService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(service: StoreTypeService):
    await service.create(_create(code="MT", name="Modern Trade"))
    await service.create(_create(code="GT", name="General Trade"))

    items = await service.list()

    assert {"Modern Trade", "General Trade"}.issubset({item.name for item in items})


async def test_update_existing(service: StoreTypeService):
    store_type = await service.create(_create())

    updated = await service.update(store_type.id, StoreTypeUpdate(name="Updated"))

    assert updated is not None
    assert updated.name == "Updated"


async def test_update_missing_returns_none(service: StoreTypeService):
    assert await service.update(uuid.uuid4(), StoreTypeUpdate(name="Updated")) is None


async def test_update_rejects_duplicate_code(service: StoreTypeService):
    await service.create(_create(code="MT"))
    other = await service.create(_create(code="GT", name="General Trade"))

    with pytest.raises(DuplicateStoreTypeCodeError):
        await service.update(other.id, StoreTypeUpdate(code="MT"))


async def test_delete_existing(service: StoreTypeService):
    store_type = await service.create(_create())

    deleted = await service.delete(store_type.id)

    assert deleted is True
    assert await service.get(store_type.id) is None


async def test_delete_missing_returns_false(service: StoreTypeService):
    assert await service.delete(uuid.uuid4()) is False
