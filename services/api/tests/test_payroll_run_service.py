import calendar
import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.core.payroll import PayrollRunStatus
from eop_api.db.base import Base
from eop_api.schemas.pagination import PaginationParams
from eop_api.schemas.payroll_run import PayrollRunCreate, PayrollRunUpdate
from eop_api.schemas.search import SearchParams
from eop_api.services.payroll_run import (
    DuplicatePayrollRunCodeError,
    InvalidPayrollPeriodError,
    InvalidPayrollRunTransitionError,
    OverlappingPayrollRunPeriodError,
    PayrollRunService,
)
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


def _month_bounds(month: int, year: int = 2026) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _create(
    code: str = "RUN-001", name: str = "First Run", *, month: int = 1, currency: str = "IDR"
) -> PayrollRunCreate:
    period_start, period_end = _month_bounds(month)
    return PayrollRunCreate(
        code=code, name=name, period_start=period_start, period_end=period_end, currency=currency
    )


async def test_create_and_get(service: PayrollRunService):
    payroll_run = await service.create(_create(code="RUN-001", name="First Run"))

    fetched = await service.get(payroll_run.id)

    assert fetched is not None
    assert fetched.code == "RUN-001"
    assert fetched.name == "First Run"
    assert fetched.period_start is not None
    assert fetched.currency == "IDR"


async def test_create_starts_in_draft(service: PayrollRunService):
    payroll_run = await service.create(_create())

    assert payroll_run.status == PayrollRunStatus.DRAFT


async def test_create_rejects_period_not_starting_on_first_of_month(service: PayrollRunService):
    with pytest.raises(InvalidPayrollPeriodError):
        await service.create(
            PayrollRunCreate(
                code="RUN-001",
                name="First Run",
                period_start=date(2026, 1, 5),
                period_end=date(2026, 1, 31),
                currency="IDR",
            )
        )


async def test_create_rejects_period_not_ending_on_last_of_month(service: PayrollRunService):
    with pytest.raises(InvalidPayrollPeriodError):
        await service.create(
            PayrollRunCreate(
                code="RUN-001",
                name="First Run",
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 30),
                currency="IDR",
            )
        )


async def test_create_rejects_period_spanning_multiple_months(service: PayrollRunService):
    with pytest.raises(InvalidPayrollPeriodError):
        await service.create(
            PayrollRunCreate(
                code="RUN-001",
                name="First Run",
                period_start=date(2026, 1, 1),
                period_end=date(2026, 2, 28),
                currency="IDR",
            )
        )


async def test_create_rejects_overlapping_period_same_currency(service: PayrollRunService):
    await service.create(_create(code="RUN-001", month=1, currency="IDR"))

    with pytest.raises(OverlappingPayrollRunPeriodError):
        await service.create(_create(code="RUN-002", month=1, currency="IDR"))


async def test_create_allows_same_period_different_currency(service: PayrollRunService):
    """D8/E7: overlap is scoped per-currency -- different currencies may
    have a run for the same month."""
    first = await service.create(_create(code="RUN-001", month=1, currency="IDR"))
    second = await service.create(_create(code="RUN-002", month=1, currency="USD"))

    assert first.id != second.id


async def test_start_processing_transitions_draft_to_processing(service: PayrollRunService):
    payroll_run = await service.create(_create())

    updated = await service.start_processing(payroll_run.id)

    assert updated is not None
    assert updated.status == PayrollRunStatus.PROCESSING


async def test_start_processing_is_idempotent_while_processing(service: PayrollRunService):
    """D9: a `PROCESSING` run may be re-entered (pre-completion rerun support)
    -- no longer rejected, per `implementation-plan.md` §3.3."""
    payroll_run = await service.create(_create())
    await service.start_processing(payroll_run.id)

    again = await service.start_processing(payroll_run.id)

    assert again is not None
    assert again.status == PayrollRunStatus.PROCESSING


async def test_start_processing_rejects_completed(service: PayrollRunService):
    """E5: immutability boundary -- a `COMPLETED` run may never re-enter processing."""
    payroll_run = await service.create(_create())
    await service.start_processing(payroll_run.id)
    await service.complete(payroll_run.id)

    with pytest.raises(InvalidPayrollRunTransitionError):
        await service.start_processing(payroll_run.id)


async def test_start_processing_missing_returns_none(service: PayrollRunService):
    assert await service.start_processing(uuid.uuid4()) is None


async def test_complete_transitions_processing_to_completed(service: PayrollRunService):
    payroll_run = await service.create(_create())
    await service.start_processing(payroll_run.id)

    updated = await service.complete(payroll_run.id)

    assert updated is not None
    assert updated.status == PayrollRunStatus.COMPLETED


async def test_complete_rejects_non_processing(service: PayrollRunService):
    payroll_run = await service.create(_create())

    with pytest.raises(InvalidPayrollRunTransitionError):
        await service.complete(payroll_run.id)


async def test_complete_missing_returns_none(service: PayrollRunService):
    assert await service.complete(uuid.uuid4()) is None


async def test_create_rejects_duplicate_code(service: PayrollRunService):
    await service.create(_create(code="RUN-001", name="First Run"))

    with pytest.raises(DuplicatePayrollRunCodeError):
        await service.create(_create(code="RUN-001", name="First Run Two"))


async def test_get_missing_returns_none(service: PayrollRunService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(service: PayrollRunService):
    await service.create(_create(code="RUN-001", name="First Run", month=1))
    await service.create(_create(code="RUN-002", name="Second Run", month=2))

    items = await service.list()

    assert {"First Run", "Second Run"}.issubset({item.name for item in items})


async def test_update_existing(service: PayrollRunService):
    payroll_run = await service.create(_create(code="RUN-001", name="Before"))

    updated = await service.update(payroll_run.id, PayrollRunUpdate(name="After"))

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(service: PayrollRunService):
    assert await service.update(uuid.uuid4(), PayrollRunUpdate(name="After")) is None


async def test_update_rejects_duplicate_code(service: PayrollRunService):
    await service.create(_create(code="RUN-001", name="First Run", month=1))
    other = await service.create(_create(code="RUN-002", name="Second Run", month=2))

    with pytest.raises(DuplicatePayrollRunCodeError):
        await service.update(other.id, PayrollRunUpdate(code="RUN-001"))


async def test_update_allows_unchanged_code(service: PayrollRunService):
    payroll_run = await service.create(_create(code="RUN-001", name="First Run"))

    updated = await service.update(
        payroll_run.id, PayrollRunUpdate(code="RUN-001", name="First Run Renamed")
    )

    assert updated is not None
    assert updated.name == "First Run Renamed"


async def test_delete_existing(service: PayrollRunService):
    payroll_run = await service.create(_create(code="RUN-001", name="To Delete"))

    deleted = await service.delete(payroll_run.id)

    assert deleted is True
    assert await service.get(payroll_run.id) is None


async def test_delete_missing_returns_false(service: PayrollRunService):
    assert await service.delete(uuid.uuid4()) is False


async def test_list_paginated_passes_through_offset_and_limit(service: PayrollRunService):
    for i in range(5):
        await service.create(_create(code=f"RUN-{i}", name=f"Run {i}", month=i + 1))

    page = await service.list_paginated(PaginationParams(offset=1, limit=2))

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_list_paginated_passes_through_search(service: PayrollRunService):
    await service.create(_create(code="RUN-001", name="August Run", month=1))
    await service.create(_create(code="RUN-002", name="September Run", month=2))

    page = await service.list_paginated(
        PaginationParams(offset=0, limit=50), SearchParams(q="august")
    )

    assert page.total == 1
    assert page.items[0].name == "August Run"
