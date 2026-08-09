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
from eop_api.repositories.kpi import KpiRepository
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
def repo(session: AsyncSession) -> KpiRepository:
    return KpiRepository(session)


async def test_create_and_get(repo: KpiRepository):
    kpi = await repo.create(
        code="VCR", name="Visit Compliance Rate", unit="%", description="Planned vs actual visits"
    )

    fetched = await repo.get(kpi.id)

    assert fetched is not None
    assert fetched.code == "VCR"
    assert fetched.name == "Visit Compliance Rate"
    assert fetched.unit == "%"
    assert fetched.description == "Planned vs actual visits"


async def test_get_missing_returns_none(repo: KpiRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_get_by_code(repo: KpiRepository):
    kpi = await repo.create(code="VCR", name="Visit Compliance Rate")

    found = await repo.get_by_code("VCR")

    assert found is not None
    assert found.id == kpi.id
    assert await repo.get_by_code("missing") is None


async def test_list_returns_created(repo: KpiRepository):
    await repo.create(code="VCR", name="Visit Compliance Rate")
    await repo.create(code="ADR", name="Average Daily Rate")

    items = await repo.list()

    assert {"Visit Compliance Rate", "Average Daily Rate"}.issubset({item.name for item in items})


async def test_update_existing(repo: KpiRepository):
    kpi = await repo.create(code="VCR", name="Before")

    updated = await repo.update(kpi.id, name="After")

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(repo: KpiRepository):
    assert await repo.update(uuid.uuid4(), name="After") is None


async def test_delete_existing(repo: KpiRepository):
    kpi = await repo.create(code="VCR", name="Visit Compliance Rate")

    deleted = await repo.delete(kpi.id)

    assert deleted is True
    assert await repo.get(kpi.id) is None


async def test_delete_missing_returns_false(repo: KpiRepository):
    assert await repo.delete(uuid.uuid4()) is False


async def test_paginate_search_returns_matching_rows(repo: KpiRepository):
    await repo.create(code="VCR", name="Visit Compliance Rate")
    await repo.create(code="ADR", name="Average Daily Rate")

    page = await repo.paginate(search=SearchParams(q="compliance"))

    assert page.total == 1
    assert page.items[0].name == "Visit Compliance Rate"


async def test_paginate_no_search_returns_all_rows(repo: KpiRepository):
    await repo.create(code="VCR", name="Visit Compliance Rate")
    await repo.create(code="ADR", name="Average Daily Rate")

    page = await repo.paginate(search=None)

    assert page.total == 2


async def test_paginate_returns_total_and_page_slice(repo: KpiRepository):
    for i in range(5):
        await repo.create(code=f"KPI-{i}", name=f"KPI {i}")

    page = await repo.paginate(offset=1, limit=2)

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2
