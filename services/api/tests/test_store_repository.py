import uuid
from collections.abc import AsyncGenerator
from decimal import Decimal

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
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.store import StoreRepository
from eop_api.repositories.store_type import StoreTypeRepository
from eop_api.schemas.search import FilterParams, SearchParams

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
def repo(session: AsyncSession) -> StoreRepository:
    return StoreRepository(session)


@pytest.fixture
async def ids(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    organization = await OrganizationRepository(session).create(name="Acme Corp")
    store_type = await StoreTypeRepository(session).create(code="MT", name="Modern Trade")
    return organization.id, store_type.id


async def test_create_and_get(repo: StoreRepository, ids: tuple[uuid.UUID, uuid.UUID]):
    organization_id, store_type_id = ids
    store = await repo.create(
        code="ST-1",
        name="Indomaret Sudirman",
        organization_id=organization_id,
        store_type_id=store_type_id,
        address="Jl. Sudirman No. 1",
        latitude=Decimal("-6.208763"),
        longitude=Decimal("106.845599"),
    )

    fetched = await repo.get(store.id)

    assert fetched is not None
    assert fetched.code == "ST-1"
    assert fetched.name == "Indomaret Sudirman"
    assert fetched.organization_id == organization_id
    assert fetched.store_type_id == store_type_id
    assert fetched.address == "Jl. Sudirman No. 1"
    assert fetched.latitude == Decimal("-6.208763")
    assert fetched.longitude == Decimal("106.845599")
    assert fetched.description is None


async def test_get_missing_returns_none(repo: StoreRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_get_by_code(repo: StoreRepository, ids: tuple[uuid.UUID, uuid.UUID]):
    organization_id, store_type_id = ids
    store = await repo.create(
        code="ST-1", name="Store 1", organization_id=organization_id, store_type_id=store_type_id
    )

    found = await repo.get_by_code("ST-1")

    assert found is not None
    assert found.id == store.id
    assert await repo.get_by_code("missing") is None


async def test_update_existing(repo: StoreRepository, ids: tuple[uuid.UUID, uuid.UUID]):
    organization_id, store_type_id = ids
    store = await repo.create(
        code="ST-1",
        name="Before",
        organization_id=organization_id,
        store_type_id=store_type_id,
    )

    updated = await repo.update(store.id, name="After")

    assert updated is not None
    assert updated.name == "After"


async def test_delete_existing(repo: StoreRepository, ids: tuple[uuid.UUID, uuid.UUID]):
    organization_id, store_type_id = ids
    store = await repo.create(
        code="ST-1", name="Store 1", organization_id=organization_id, store_type_id=store_type_id
    )

    deleted = await repo.delete(store.id)

    assert deleted is True
    assert await repo.get(store.id) is None


async def test_paginate_search_by_name(repo: StoreRepository, ids: tuple[uuid.UUID, uuid.UUID]):
    organization_id, store_type_id = ids
    await repo.create(
        code="ST-1",
        name="Indomaret Sudirman",
        organization_id=organization_id,
        store_type_id=store_type_id,
    )
    await repo.create(
        code="ST-2",
        name="Alfamart Thamrin",
        organization_id=organization_id,
        store_type_id=store_type_id,
    )

    page = await repo.paginate(search=SearchParams(q="indomaret"))

    assert page.total == 1
    assert page.items[0].name == "Indomaret Sudirman"


async def test_paginate_filters_by_store_type_id(
    repo: StoreRepository, session: AsyncSession, ids: tuple[uuid.UUID, uuid.UUID]
):
    organization_id, store_type_id = ids
    other_store_type = await StoreTypeRepository(session).create(code="GT", name="General Trade")
    await repo.create(
        code="ST-1",
        name="Indomaret Sudirman",
        organization_id=organization_id,
        store_type_id=store_type_id,
    )
    await repo.create(
        code="ST-2",
        name="Warung Pak Budi",
        organization_id=organization_id,
        store_type_id=other_store_type.id,
    )

    page = await repo.paginate(filters=FilterParams(values={"store_type_id": store_type_id}))

    assert page.total == 1
    assert page.items[0].name == "Indomaret Sudirman"


async def test_paginate_filters_by_organization_id(
    repo: StoreRepository, session: AsyncSession, ids: tuple[uuid.UUID, uuid.UUID]
):
    organization_id, store_type_id = ids
    other_organization = await OrganizationRepository(session).create(name="Other Corp")
    await repo.create(
        code="ST-1", name="Store 1", organization_id=organization_id, store_type_id=store_type_id
    )
    await repo.create(
        code="ST-2",
        name="Store 2",
        organization_id=other_organization.id,
        store_type_id=store_type_id,
    )

    page = await repo.paginate(filters=FilterParams(values={"organization_id": organization_id}))

    assert page.total == 1
    assert page.items[0].code == "ST-1"
