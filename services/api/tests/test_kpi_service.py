import uuid
from collections.abc import AsyncGenerator, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.schemas.kpi import KpiCreate, KpiUpdate
from eop_api.schemas.pagination import PaginationParams
from eop_api.schemas.search import SearchParams
from eop_api.services.kpi import DuplicateKpiCodeError, KpiService
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
            await conn.execute(text("TRUNCATE TABLE kpis CASCADE"))
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> KpiService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return KpiService(uow_factory)


def _create(code: str = "VCR", **overrides) -> KpiCreate:
    values = {"code": code, "name": "Visit Compliance Rate", "unit": "%"}
    values.update(overrides)
    return KpiCreate(**values)


async def test_create_and_get(service: KpiService):
    kpi = await service.create(_create())

    fetched = await service.get(kpi.id)

    assert fetched is not None
    assert fetched.code == "VCR"
    assert fetched.name == "Visit Compliance Rate"
    assert fetched.unit == "%"


async def test_create_rejects_duplicate_code(service: KpiService):
    await service.create(_create(code="VCR"))

    with pytest.raises(DuplicateKpiCodeError):
        await service.create(_create(code="VCR", name="Other"))


async def test_get_missing_returns_none(service: KpiService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(service: KpiService):
    await service.create(_create(code="VCR", name="Visit Compliance Rate"))
    await service.create(_create(code="ADR", name="Average Daily Rate"))

    items = await service.list()

    assert {"Visit Compliance Rate", "Average Daily Rate"}.issubset({item.name for item in items})


async def test_list_paginated_passes_through_search(service: KpiService):
    await service.create(_create(code="VCR", name="Visit Compliance Rate"))
    await service.create(_create(code="ADR", name="Average Daily Rate"))

    page = await service.list_paginated(
        PaginationParams(offset=0, limit=50), SearchParams(q="daily")
    )

    assert page.total == 1
    assert page.items[0].name == "Average Daily Rate"


async def test_update_existing(service: KpiService):
    kpi = await service.create(_create())

    updated = await service.update(kpi.id, KpiUpdate(name="Updated"))

    assert updated is not None
    assert updated.name == "Updated"


async def test_update_missing_returns_none(service: KpiService):
    assert await service.update(uuid.uuid4(), KpiUpdate(name="Updated")) is None


async def test_update_rejects_duplicate_code(service: KpiService):
    await service.create(_create(code="VCR"))
    other = await service.create(_create(code="ADR", name="Average Daily Rate"))

    with pytest.raises(DuplicateKpiCodeError):
        await service.update(other.id, KpiUpdate(code="VCR"))


async def test_delete_existing(service: KpiService):
    kpi = await service.create(_create())

    deleted = await service.delete(kpi.id)

    assert deleted is True
    assert await service.get(kpi.id) is None


async def test_delete_missing_returns_false(service: KpiService):
    assert await service.delete(uuid.uuid4()) is False
