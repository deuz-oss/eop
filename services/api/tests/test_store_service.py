import uuid
from collections.abc import AsyncGenerator, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.store_type import StoreTypeRepository
from eop_api.schemas.store import StoreCreate, StoreUpdate
from eop_api.services.store import (
    DuplicateStoreCodeError,
    OrganizationNotFoundError,
    StoreService,
    StoreTypeNotFoundError,
)
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
            await conn.execute(text("TRUNCATE TABLE organizations, store_types CASCADE"))
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> StoreService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return StoreService(uow_factory)


@pytest.fixture
async def ids(session_factory: Callable[[], AsyncSession]) -> tuple[uuid.UUID, uuid.UUID]:
    async with session_factory() as session:
        organization = await OrganizationRepository(session).create(name="Acme Corp")
        store_type = await StoreTypeRepository(session).create(code="MT", name="Modern Trade")
        await session.commit()
        return organization.id, store_type.id


def _create(ids: tuple[uuid.UUID, uuid.UUID], code: str = "ST-1", **overrides) -> StoreCreate:
    organization_id, store_type_id = ids
    values = {
        "code": code,
        "name": "Indomaret Sudirman",
        "organization_id": organization_id,
        "store_type_id": store_type_id,
    }
    values.update(overrides)
    return StoreCreate(**values)


async def test_create_and_get(service: StoreService, ids: tuple[uuid.UUID, uuid.UUID]):
    store = await service.create(_create(ids))

    fetched = await service.get(store.id)

    assert fetched is not None
    assert fetched.code == "ST-1"
    assert fetched.name == "Indomaret Sudirman"


async def test_create_rejects_duplicate_code(
    service: StoreService, ids: tuple[uuid.UUID, uuid.UUID]
):
    await service.create(_create(ids, code="ST-1"))

    with pytest.raises(DuplicateStoreCodeError):
        await service.create(_create(ids, code="ST-1", name="Other"))


async def test_create_rejects_missing_organization(
    service: StoreService, ids: tuple[uuid.UUID, uuid.UUID]
):
    with pytest.raises(OrganizationNotFoundError):
        await service.create(_create(ids, organization_id=uuid.uuid4()))


async def test_create_rejects_missing_store_type(
    service: StoreService, ids: tuple[uuid.UUID, uuid.UUID]
):
    with pytest.raises(StoreTypeNotFoundError):
        await service.create(_create(ids, store_type_id=uuid.uuid4()))


async def test_get_missing_returns_none(service: StoreService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(service: StoreService, ids: tuple[uuid.UUID, uuid.UUID]):
    await service.create(_create(ids, code="ST-1"))
    await service.create(_create(ids, code="ST-2", name="Alfamart Thamrin"))

    items = await service.list()

    assert {"Indomaret Sudirman", "Alfamart Thamrin"}.issubset({item.name for item in items})


async def test_update_existing(service: StoreService, ids: tuple[uuid.UUID, uuid.UUID]):
    store = await service.create(_create(ids))

    updated = await service.update(store.id, StoreUpdate(name="Updated"))

    assert updated is not None
    assert updated.name == "Updated"


async def test_update_missing_returns_none(service: StoreService):
    assert await service.update(uuid.uuid4(), StoreUpdate(name="Updated")) is None


async def test_update_rejects_duplicate_code(
    service: StoreService, ids: tuple[uuid.UUID, uuid.UUID]
):
    await service.create(_create(ids, code="ST-1"))
    other = await service.create(_create(ids, code="ST-2", name="Other"))

    with pytest.raises(DuplicateStoreCodeError):
        await service.update(other.id, StoreUpdate(code="ST-1"))


async def test_update_rejects_missing_organization(
    service: StoreService, ids: tuple[uuid.UUID, uuid.UUID]
):
    store = await service.create(_create(ids))

    with pytest.raises(OrganizationNotFoundError):
        await service.update(store.id, StoreUpdate(organization_id=uuid.uuid4()))


async def test_update_rejects_missing_store_type(
    service: StoreService, ids: tuple[uuid.UUID, uuid.UUID]
):
    store = await service.create(_create(ids))

    with pytest.raises(StoreTypeNotFoundError):
        await service.update(store.id, StoreUpdate(store_type_id=uuid.uuid4()))


async def test_delete_existing(service: StoreService, ids: tuple[uuid.UUID, uuid.UUID]):
    store = await service.create(_create(ids))

    deleted = await service.delete(store.id)

    assert deleted is True
    assert await service.get(store.id) is None


async def test_delete_missing_returns_false(service: StoreService):
    assert await service.delete(uuid.uuid4()) is False
