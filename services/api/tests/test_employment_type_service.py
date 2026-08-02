import uuid
from collections.abc import AsyncGenerator, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.schemas.employment_type import EmploymentTypeCreate, EmploymentTypeUpdate
from eop_api.schemas.pagination import PaginationParams
from eop_api.schemas.search import SearchParams
from eop_api.services.employment_type import (
    DuplicateEmploymentTypeCodeError,
    EmploymentTypeService,
)
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session_factory() -> AsyncGenerator[Callable[[], AsyncSession]]:
    """A session factory backed by the real (migration-managed) `employment_types` table.

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
            await conn.execute(text("TRUNCATE TABLE employment_types CASCADE"))
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> EmploymentTypeService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return EmploymentTypeService(uow_factory)


async def test_create_and_get(service: EmploymentTypeService):
    employment_type = await service.create(EmploymentTypeCreate(code="FT", name="Full-Time"))

    fetched = await service.get(employment_type.id)

    assert fetched is not None
    assert fetched.code == "FT"
    assert fetched.name == "Full-Time"


async def test_create_rejects_duplicate_code(service: EmploymentTypeService):
    await service.create(EmploymentTypeCreate(code="FT", name="Full-Time"))

    with pytest.raises(DuplicateEmploymentTypeCodeError):
        await service.create(EmploymentTypeCreate(code="FT", name="Full-Time Two"))


async def test_get_missing_returns_none(service: EmploymentTypeService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(service: EmploymentTypeService):
    await service.create(EmploymentTypeCreate(code="FT", name="Full-Time"))
    await service.create(EmploymentTypeCreate(code="PT", name="Part-Time"))

    items = await service.list()

    assert {"Full-Time", "Part-Time"}.issubset({item.name for item in items})


async def test_update_existing(service: EmploymentTypeService):
    employment_type = await service.create(EmploymentTypeCreate(code="FT", name="Before"))

    updated = await service.update(employment_type.id, EmploymentTypeUpdate(name="After"))

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(service: EmploymentTypeService):
    assert await service.update(uuid.uuid4(), EmploymentTypeUpdate(name="After")) is None


async def test_update_rejects_duplicate_code(service: EmploymentTypeService):
    await service.create(EmploymentTypeCreate(code="FT", name="Full-Time"))
    other = await service.create(EmploymentTypeCreate(code="PT", name="Part-Time"))

    with pytest.raises(DuplicateEmploymentTypeCodeError):
        await service.update(other.id, EmploymentTypeUpdate(code="FT"))


async def test_update_allows_unchanged_code(service: EmploymentTypeService):
    employment_type = await service.create(EmploymentTypeCreate(code="FT", name="Full-Time"))

    updated = await service.update(
        employment_type.id, EmploymentTypeUpdate(code="FT", name="Full-Time Renamed")
    )

    assert updated is not None
    assert updated.name == "Full-Time Renamed"


async def test_delete_existing(service: EmploymentTypeService):
    employment_type = await service.create(EmploymentTypeCreate(code="FT", name="To Delete"))

    deleted = await service.delete(employment_type.id)

    assert deleted is True
    assert await service.get(employment_type.id) is None


async def test_delete_missing_returns_false(service: EmploymentTypeService):
    assert await service.delete(uuid.uuid4()) is False


async def test_list_paginated_passes_through_offset_and_limit(service: EmploymentTypeService):
    for i in range(5):
        await service.create(EmploymentTypeCreate(code=f"T{i}", name=f"Type {i}"))

    page = await service.list_paginated(PaginationParams(offset=1, limit=2))

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_list_paginated_passes_through_search(service: EmploymentTypeService):
    await service.create(EmploymentTypeCreate(code="FT", name="Full-Time"))
    await service.create(EmploymentTypeCreate(code="PT", name="Part-Time"))

    page = await service.list_paginated(
        PaginationParams(offset=0, limit=50), SearchParams(q="full")
    )

    assert page.total == 1
    assert page.items[0].name == "Full-Time"
