import uuid
from collections.abc import AsyncGenerator, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.models.location_type import LocationType
from eop_api.repositories.location_type import LocationTypeRepository
from eop_api.schemas.location import LocationCreate, LocationUpdate
from eop_api.schemas.pagination import PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.services.location import (
    DuplicateLocationCodeError,
    LocationService,
    LocationTypeNotFoundError,
    ParentLocationNotFoundError,
    SelfParentLocationError,
)
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session_factory() -> AsyncGenerator[Callable[[], AsyncSession]]:
    """A session factory backed by the real (migration-managed) `locations` table.

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
            await conn.execute(text("TRUNCATE TABLE locations, location_types CASCADE"))
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> LocationService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return LocationService(uow_factory)


@pytest.fixture
async def location_type(session_factory: Callable[[], AsyncSession]) -> LocationType:
    async with session_factory() as session:
        location_type = await LocationTypeRepository(session).create(code="store", name="Store")
        await session.commit()
        session.expunge(location_type)
        return location_type


async def test_create_and_get(service: LocationService, location_type: LocationType):
    location = await service.create(
        LocationCreate(name="Headquarters", code="HQ-1", location_type_id=location_type.id)
    )

    fetched = await service.get(location.id)

    assert fetched is not None
    assert fetched.name == "Headquarters"
    assert fetched.code == "HQ-1"
    assert fetched.location_type_id == location_type.id


async def test_create_with_parent(service: LocationService, location_type: LocationType):
    parent = await service.create(
        LocationCreate(name="Headquarters", code="HQ-1", location_type_id=location_type.id)
    )

    child = await service.create(
        LocationCreate(
            name="Region A",
            code="REG-A",
            location_type_id=location_type.id,
            parent_id=parent.id,
        )
    )

    assert child.parent_id == parent.id


async def test_create_rejects_missing_parent(service: LocationService, location_type: LocationType):
    with pytest.raises(ParentLocationNotFoundError):
        await service.create(
            LocationCreate(
                name="Region A",
                code="REG-A",
                location_type_id=location_type.id,
                parent_id=uuid.uuid4(),
            )
        )


async def test_create_rejects_missing_location_type(service: LocationService):
    with pytest.raises(LocationTypeNotFoundError):
        await service.create(
            LocationCreate(name="Store One", code="S-1", location_type_id=uuid.uuid4())
        )


async def test_create_rejects_duplicate_code(service: LocationService, location_type: LocationType):
    await service.create(
        LocationCreate(name="Store One", code="S-1", location_type_id=location_type.id)
    )

    with pytest.raises(DuplicateLocationCodeError):
        await service.create(
            LocationCreate(name="Store Two", code="S-1", location_type_id=location_type.id)
        )


async def test_get_missing_returns_none(service: LocationService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(service: LocationService, location_type: LocationType):
    await service.create(
        LocationCreate(name="Alpha", code="A-1", location_type_id=location_type.id)
    )
    await service.create(LocationCreate(name="Beta", code="B-1", location_type_id=location_type.id))

    items = await service.list()

    assert {"Alpha", "Beta"}.issubset({item.name for item in items})


async def test_update_existing(service: LocationService, location_type: LocationType):
    location = await service.create(
        LocationCreate(name="Before", code="C-1", location_type_id=location_type.id)
    )

    updated = await service.update(location.id, LocationUpdate(name="After"))

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(service: LocationService):
    assert await service.update(uuid.uuid4(), LocationUpdate(name="After")) is None


async def test_update_rejects_missing_parent(service: LocationService, location_type: LocationType):
    location = await service.create(
        LocationCreate(name="Region A", code="REG-A", location_type_id=location_type.id)
    )

    with pytest.raises(ParentLocationNotFoundError):
        await service.update(location.id, LocationUpdate(parent_id=uuid.uuid4()))


async def test_update_accepts_existing_parent(
    service: LocationService, location_type: LocationType
):
    parent = await service.create(
        LocationCreate(name="Headquarters", code="HQ-1", location_type_id=location_type.id)
    )
    child = await service.create(
        LocationCreate(name="Region A", code="REG-A", location_type_id=location_type.id)
    )

    updated = await service.update(child.id, LocationUpdate(parent_id=parent.id))

    assert updated is not None
    assert updated.parent_id == parent.id


async def test_update_rejects_self_parent(service: LocationService, location_type: LocationType):
    location = await service.create(
        LocationCreate(name="Headquarters", code="HQ-1", location_type_id=location_type.id)
    )

    with pytest.raises(SelfParentLocationError):
        await service.update(location.id, LocationUpdate(parent_id=location.id))


async def test_update_rejects_missing_location_type(
    service: LocationService, location_type: LocationType
):
    location = await service.create(
        LocationCreate(name="Headquarters", code="HQ-1", location_type_id=location_type.id)
    )

    with pytest.raises(LocationTypeNotFoundError):
        await service.update(location.id, LocationUpdate(location_type_id=uuid.uuid4()))


async def test_update_rejects_duplicate_code(service: LocationService, location_type: LocationType):
    await service.create(
        LocationCreate(name="Store One", code="S-1", location_type_id=location_type.id)
    )
    other = await service.create(
        LocationCreate(name="Store Two", code="S-2", location_type_id=location_type.id)
    )

    with pytest.raises(DuplicateLocationCodeError):
        await service.update(other.id, LocationUpdate(code="S-1"))


async def test_update_allows_unchanged_code(service: LocationService, location_type: LocationType):
    location = await service.create(
        LocationCreate(name="Store", code="S-1", location_type_id=location_type.id)
    )

    updated = await service.update(location.id, LocationUpdate(code="S-1", name="Store Renamed"))

    assert updated is not None
    assert updated.name == "Store Renamed"


async def test_delete_existing(service: LocationService, location_type: LocationType):
    location = await service.create(
        LocationCreate(name="To Delete", code="D-1", location_type_id=location_type.id)
    )

    deleted = await service.delete(location.id)

    assert deleted is True
    assert await service.get(location.id) is None


async def test_delete_missing_returns_false(service: LocationService):
    assert await service.delete(uuid.uuid4()) is False


async def test_delete_parent_with_children_is_restricted(
    service: LocationService, location_type: LocationType
):
    parent = await service.create(
        LocationCreate(name="Headquarters", code="HQ-1", location_type_id=location_type.id)
    )
    await service.create(
        LocationCreate(
            name="Region A", code="REG-A", location_type_id=location_type.id, parent_id=parent.id
        )
    )

    with pytest.raises(IntegrityError):
        await service.delete(parent.id)


async def test_list_paginated_passes_through_offset_and_limit(
    service: LocationService, location_type: LocationType
):
    for i in range(5):
        await service.create(
            LocationCreate(name=f"Store {i}", code=f"S-{i}", location_type_id=location_type.id)
        )

    page = await service.list_paginated(PaginationParams(offset=1, limit=2))

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_list_paginated_passes_through_search(
    service: LocationService, location_type: LocationType
):
    await service.create(
        LocationCreate(name="Open Warehouse", code="W-1", location_type_id=location_type.id)
    )
    await service.create(
        LocationCreate(name="Closed Store", code="S-1", location_type_id=location_type.id)
    )

    page = await service.list_paginated(
        PaginationParams(offset=0, limit=50), SearchParams(q="open")
    )

    assert page.total == 1
    assert page.items[0].name == "Open Warehouse"


async def test_list_paginated_passes_through_filters(
    service: LocationService, session_factory: Callable[[], AsyncSession]
) -> None:
    async with session_factory() as session:
        type_repo = LocationTypeRepository(session)
        warehouse = await type_repo.create(code="warehouse", name="Warehouse")
        store = await type_repo.create(code="store", name="Store")
        await session.commit()
        session.expunge(warehouse)
        session.expunge(store)

    await service.create(
        LocationCreate(name="Main Warehouse", code="W-1", location_type_id=warehouse.id)
    )
    await service.create(LocationCreate(name="Main Store", code="S-1", location_type_id=store.id))

    page = await service.list_paginated(
        PaginationParams(offset=0, limit=50),
        filters=FilterParams(values={"location_type_id": warehouse.id}),
    )

    assert page.total == 1
    assert page.items[0].location_type_id == warehouse.id
