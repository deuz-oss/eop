import uuid
from collections.abc import AsyncGenerator, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.schemas.organization import OrganizationCreate, OrganizationUpdate
from eop_api.schemas.pagination import PaginationParams
from eop_api.schemas.search import SearchParams
from eop_api.services.organization import OrganizationService
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def service() -> AsyncGenerator[OrganizationService]:
    """A service backed by the real (migration-managed) `organizations` table.

    Unlike the repository tests, the service commits internally (it owns the
    transaction boundary), so rows are truncated after each test instead of
    relying on a rolled-back transaction.
    """
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory: Callable[[], AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(session_factory)  # noqa: E731

    try:
        yield OrganizationService(uow_factory)
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE organizations CASCADE"))
        await engine.dispose()


async def test_create_and_get(service: OrganizationService):
    organization = await service.create(OrganizationCreate(name="Acme Corp"))

    fetched = await service.get(organization.id)

    assert fetched is not None
    assert fetched.name == "Acme Corp"


async def test_get_missing_returns_none(service: OrganizationService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(service: OrganizationService):
    await service.create(OrganizationCreate(name="Alpha"))
    await service.create(OrganizationCreate(name="Beta"))

    items = await service.list()

    assert {"Alpha", "Beta"}.issubset({item.name for item in items})


async def test_update_existing(service: OrganizationService):
    organization = await service.create(OrganizationCreate(name="Before"))

    updated = await service.update(organization.id, OrganizationUpdate(name="After"))

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(service: OrganizationService):
    assert await service.update(uuid.uuid4(), OrganizationUpdate(name="After")) is None


async def test_delete_existing(service: OrganizationService):
    organization = await service.create(OrganizationCreate(name="To Delete"))

    deleted = await service.delete(organization.id)

    assert deleted is True
    assert await service.get(organization.id) is None


async def test_delete_missing_returns_false(service: OrganizationService):
    assert await service.delete(uuid.uuid4()) is False


async def test_list_paginated_passes_through_offset_and_limit(service: OrganizationService):
    for i in range(5):
        await service.create(OrganizationCreate(name=f"Org {i}"))

    page = await service.list_paginated(PaginationParams(offset=1, limit=2))

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_list_paginated_defaults(service: OrganizationService):
    await service.create(OrganizationCreate(name="Solo"))

    page = await service.list_paginated(PaginationParams(offset=0, limit=50))

    assert page.total == 1
    assert page.offset == 0
    assert page.limit == 50
    assert len(page.items) == 1


async def test_list_paginated_passes_through_search(service: OrganizationService):
    await service.create(OrganizationCreate(name="Open Robotics"))
    await service.create(OrganizationCreate(name="Closed Systems"))

    page = await service.list_paginated(
        PaginationParams(offset=0, limit=50), SearchParams(q="open")
    )

    assert page.total == 1
    assert page.items[0].name == "Open Robotics"


async def test_list_paginated_without_search_returns_all(service: OrganizationService):
    await service.create(OrganizationCreate(name="Alpha"))
    await service.create(OrganizationCreate(name="Beta"))

    page = await service.list_paginated(PaginationParams(offset=0, limit=50))

    assert page.total == 2


async def test_create_commits_and_is_visible_from_a_new_session(service: OrganizationService):
    organization = await service.create(OrganizationCreate(name="Persisted"))

    fetched = await service.get(organization.id)

    assert fetched is not None
    assert fetched.id == organization.id
