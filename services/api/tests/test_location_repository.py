import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.models.location_type import LocationType
from eop_api.repositories.location import LocationRepository
from eop_api.repositories.location_type import LocationTypeRepository
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
def repo(session: AsyncSession) -> LocationRepository:
    return LocationRepository(session)


@pytest.fixture
def location_type_repo(session: AsyncSession) -> LocationTypeRepository:
    return LocationTypeRepository(session)


@pytest.fixture
async def location_type(location_type_repo: LocationTypeRepository) -> LocationType:
    return await location_type_repo.create(code="store", name="Store")


async def test_create_and_get(repo: LocationRepository, location_type: LocationType):
    location = await repo.create(
        name="Headquarters", code="HQ-1", location_type_id=location_type.id
    )

    fetched = await repo.get(location.id)

    assert fetched is not None
    assert fetched.name == "Headquarters"
    assert fetched.code == "HQ-1"
    assert fetched.location_type_id == location_type.id
    assert fetched.parent_id is None


async def test_create_with_parent(repo: LocationRepository, location_type: LocationType):
    parent = await repo.create(name="Headquarters", code="HQ-1", location_type_id=location_type.id)

    child = await repo.create(
        name="Region A",
        code="REG-A",
        location_type_id=location_type.id,
        parent_id=parent.id,
    )

    fetched = await repo.get(child.id)

    assert fetched is not None
    assert fetched.parent_id == parent.id


async def test_get_missing_returns_none(repo: LocationRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_list_returns_created(repo: LocationRepository, location_type: LocationType):
    await repo.create(name="Alpha", code="A-1", location_type_id=location_type.id)
    await repo.create(name="Beta", code="B-1", location_type_id=location_type.id)

    items = await repo.list()

    assert {"Alpha", "Beta"}.issubset({item.name for item in items})


async def test_update_existing(repo: LocationRepository, location_type: LocationType):
    location = await repo.create(name="Before", code="C-1", location_type_id=location_type.id)

    updated = await repo.update(location.id, name="After")

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(repo: LocationRepository):
    assert await repo.update(uuid.uuid4(), name="After") is None


async def test_delete_existing(repo: LocationRepository, location_type: LocationType):
    location = await repo.create(name="To Delete", code="D-1", location_type_id=location_type.id)

    deleted = await repo.delete(location.id)

    assert deleted is True
    assert await repo.get(location.id) is None


async def test_delete_missing_returns_false(repo: LocationRepository):
    assert await repo.delete(uuid.uuid4()) is False


async def test_delete_parent_with_children_is_restricted(
    repo: LocationRepository, location_type: LocationType
):
    parent = await repo.create(name="Headquarters", code="HQ-1", location_type_id=location_type.id)
    await repo.create(
        name="Region A", code="REG-A", location_type_id=location_type.id, parent_id=parent.id
    )

    with pytest.raises(IntegrityError):
        await repo.delete(parent.id)


async def test_get_by_code(repo: LocationRepository, location_type: LocationType):
    location = await repo.create(name="Store", code="S-1", location_type_id=location_type.id)

    found = await repo.get_by_code("S-1")

    assert found is not None
    assert found.id == location.id
    assert await repo.get_by_code("missing") is None


async def test_paginate_returns_total_and_page_slice(
    repo: LocationRepository, location_type: LocationType
):
    for i in range(5):
        await repo.create(name=f"Store {i}", code=f"S-{i}", location_type_id=location_type.id)

    page = await repo.paginate(offset=1, limit=2)

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_paginate_defaults(repo: LocationRepository, location_type: LocationType):
    for i in range(3):
        await repo.create(name=f"Store {i}", code=f"S-{i}", location_type_id=location_type.id)

    page = await repo.paginate()

    assert page.offset == 0
    assert page.limit == 50
    assert page.total == 3
    assert len(page.items) == 3


async def test_paginate_search_returns_matching_rows_by_name(
    repo: LocationRepository, location_type: LocationType
):
    await repo.create(name="Open Warehouse", code="W-1", location_type_id=location_type.id)
    await repo.create(name="Closed Store", code="S-1", location_type_id=location_type.id)

    page = await repo.paginate(search=SearchParams(q="open"))

    assert page.total == 1
    assert page.items[0].name == "Open Warehouse"


async def test_paginate_search_returns_matching_rows_by_code(
    repo: LocationRepository, location_type: LocationType
):
    await repo.create(name="Warehouse", code="WH-ALPHA", location_type_id=location_type.id)
    await repo.create(name="Store", code="ST-BETA", location_type_id=location_type.id)

    page = await repo.paginate(search=SearchParams(q="alpha"))

    assert page.total == 1
    assert page.items[0].code == "WH-ALPHA"


async def test_paginate_no_search_returns_all_rows(
    repo: LocationRepository, location_type: LocationType
):
    await repo.create(name="Alpha", code="A-1", location_type_id=location_type.id)
    await repo.create(name="Beta", code="B-1", location_type_id=location_type.id)

    page = await repo.paginate(search=None)

    assert page.total == 2


async def test_paginate_filters_by_location_type_id(
    repo: LocationRepository, location_type_repo: LocationTypeRepository
):
    warehouse = await location_type_repo.create(code="warehouse", name="Warehouse")
    store = await location_type_repo.create(code="store", name="Store")
    await repo.create(name="Main Warehouse", code="W-1", location_type_id=warehouse.id)
    await repo.create(name="Main Store", code="S-1", location_type_id=store.id)

    page = await repo.paginate(filters=FilterParams(values={"location_type_id": warehouse.id}))

    assert page.total == 1
    assert page.items[0].location_type_id == warehouse.id


async def test_paginate_without_filters_returns_all_rows(
    repo: LocationRepository, location_type_repo: LocationTypeRepository
):
    warehouse = await location_type_repo.create(code="warehouse", name="Warehouse")
    store = await location_type_repo.create(code="store", name="Store")
    await repo.create(name="Main Warehouse", code="W-1", location_type_id=warehouse.id)
    await repo.create(name="Main Store", code="S-1", location_type_id=store.id)

    page = await repo.paginate()

    assert page.total == 2
