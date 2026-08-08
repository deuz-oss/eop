import uuid
from collections.abc import AsyncGenerator, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.schemas.pagination import PaginationParams
from eop_api.schemas.payroll_run import PayrollRunCreate, PayrollRunUpdate
from eop_api.schemas.search import SearchParams
from eop_api.services.payroll_run import DuplicatePayrollRunCodeError, PayrollRunService
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session_factory() -> AsyncGenerator[Callable[[], AsyncSession]]:
    """A session factory backed by the real (migration-managed) `payroll_runs` table.

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
            await conn.execute(text("TRUNCATE TABLE payroll_runs CASCADE"))
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> PayrollRunService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return PayrollRunService(uow_factory)


async def test_create_and_get(service: PayrollRunService):
    payroll_run = await service.create(PayrollRunCreate(code="RUN-001", name="First Run"))

    fetched = await service.get(payroll_run.id)

    assert fetched is not None
    assert fetched.code == "RUN-001"
    assert fetched.name == "First Run"


async def test_create_rejects_duplicate_code(service: PayrollRunService):
    await service.create(PayrollRunCreate(code="RUN-001", name="First Run"))

    with pytest.raises(DuplicatePayrollRunCodeError):
        await service.create(PayrollRunCreate(code="RUN-001", name="First Run Two"))


async def test_get_missing_returns_none(service: PayrollRunService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(service: PayrollRunService):
    await service.create(PayrollRunCreate(code="RUN-001", name="First Run"))
    await service.create(PayrollRunCreate(code="RUN-002", name="Second Run"))

    items = await service.list()

    assert {"First Run", "Second Run"}.issubset({item.name for item in items})


async def test_update_existing(service: PayrollRunService):
    payroll_run = await service.create(PayrollRunCreate(code="RUN-001", name="Before"))

    updated = await service.update(payroll_run.id, PayrollRunUpdate(name="After"))

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(service: PayrollRunService):
    assert await service.update(uuid.uuid4(), PayrollRunUpdate(name="After")) is None


async def test_update_rejects_duplicate_code(service: PayrollRunService):
    await service.create(PayrollRunCreate(code="RUN-001", name="First Run"))
    other = await service.create(PayrollRunCreate(code="RUN-002", name="Second Run"))

    with pytest.raises(DuplicatePayrollRunCodeError):
        await service.update(other.id, PayrollRunUpdate(code="RUN-001"))


async def test_update_allows_unchanged_code(service: PayrollRunService):
    payroll_run = await service.create(PayrollRunCreate(code="RUN-001", name="First Run"))

    updated = await service.update(
        payroll_run.id, PayrollRunUpdate(code="RUN-001", name="First Run Renamed")
    )

    assert updated is not None
    assert updated.name == "First Run Renamed"


async def test_delete_existing(service: PayrollRunService):
    payroll_run = await service.create(PayrollRunCreate(code="RUN-001", name="To Delete"))

    deleted = await service.delete(payroll_run.id)

    assert deleted is True
    assert await service.get(payroll_run.id) is None


async def test_delete_missing_returns_false(service: PayrollRunService):
    assert await service.delete(uuid.uuid4()) is False


async def test_list_paginated_passes_through_offset_and_limit(service: PayrollRunService):
    for i in range(5):
        await service.create(PayrollRunCreate(code=f"RUN-{i}", name=f"Run {i}"))

    page = await service.list_paginated(PaginationParams(offset=1, limit=2))

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_list_paginated_passes_through_search(service: PayrollRunService):
    await service.create(PayrollRunCreate(code="RUN-001", name="August Run"))
    await service.create(PayrollRunCreate(code="RUN-002", name="September Run"))

    page = await service.list_paginated(
        PaginationParams(offset=0, limit=50), SearchParams(q="august")
    )

    assert page.total == 1
    assert page.items[0].name == "August Run"
