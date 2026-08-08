import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.repositories.payroll_statutory_parameter import PayrollStatutoryParameterRepository
from eop_api.schemas.payroll_statutory_parameter import (
    PayrollStatutoryParameterCreate,
    PayrollStatutoryParameterUpdate,
)
from eop_api.services.effective_dating_evaluator import AmbiguousEffectiveStateError
from eop_api.services.payroll_statutory_parameter import (
    MissingStatutoryParameterError,
    OverlappingStatutoryParameterPeriodError,
    PayrollStatutoryParameterService,
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
            await conn.execute(text("TRUNCATE TABLE payroll_statutory_parameters CASCADE"))
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> PayrollStatutoryParameterService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return PayrollStatutoryParameterService(uow_factory)


def _create(key: str = "STATUTORY_TAX_RATE", **overrides) -> PayrollStatutoryParameterCreate:
    values = {"key": key, "value": Decimal("0.05"), "effective_from": date(2026, 1, 1)}
    values.update(overrides)
    return PayrollStatutoryParameterCreate(**values)


async def test_create_and_get(service: PayrollStatutoryParameterService):
    parameter = await service.create(_create())

    fetched = await service.get(parameter.id)

    assert fetched is not None
    assert fetched.key == "STATUTORY_TAX_RATE"
    assert fetched.value == Decimal("0.05")


async def test_create_rejects_overlapping_period_same_key(
    service: PayrollStatutoryParameterService,
):
    await service.create(_create(effective_from=date(2026, 1, 1), effective_to=date(2026, 6, 30)))

    with pytest.raises(OverlappingStatutoryParameterPeriodError):
        await service.create(
            _create(effective_from=date(2026, 3, 1), effective_to=date(2026, 9, 30))
        )


async def test_create_allows_overlapping_period_different_key(
    service: PayrollStatutoryParameterService,
):
    await service.create(_create(key="STATUTORY_TAX_RATE", effective_from=date(2026, 1, 1)))

    other = await service.create(
        _create(key="OVERTIME_MULTIPLIER_WEEKDAY", effective_from=date(2026, 1, 1))
    )

    assert other.key == "OVERTIME_MULTIPLIER_WEEKDAY"


async def test_get_value_resolves_correct_historical_row(
    service: PayrollStatutoryParameterService,
):
    await service.create(
        _create(
            value=Decimal("0.05"), effective_from=date(2026, 1, 1), effective_to=date(2026, 6, 30)
        )
    )
    await service.create(_create(value=Decimal("0.07"), effective_from=date(2026, 7, 1)))

    earlier = await service.get_value("STATUTORY_TAX_RATE", date(2026, 3, 1))
    later = await service.get_value("STATUTORY_TAX_RATE", date(2026, 9, 1))

    assert earlier == Decimal("0.05")
    assert later == Decimal("0.07")


async def test_get_value_raises_when_unconfigured(service: PayrollStatutoryParameterService):
    with pytest.raises(MissingStatutoryParameterError):
        await service.get_value("STATUTORY_TAX_RATE", date(2026, 1, 1))


async def test_get_value_or_default_returns_default_when_unconfigured(
    service: PayrollStatutoryParameterService,
):
    value = await service.get_value_or_default("STATUTORY_TAX_RATE", date(2026, 1, 1), Decimal(0))

    assert value == Decimal(0)


async def test_get_value_or_default_returns_configured_value(
    service: PayrollStatutoryParameterService,
):
    await service.create(_create(value=Decimal("0.05")))

    value = await service.get_value_or_default("STATUTORY_TAX_RATE", date(2026, 3, 1), Decimal(0))

    assert value == Decimal("0.05")


async def test_get_value_raises_on_unrelated_ambiguous_rows(
    service: PayrollStatutoryParameterService,
    session_factory: Callable[[], AsyncSession],
):
    async with session_factory() as session:
        repo = PayrollStatutoryParameterRepository(session)
        await repo.create(
            key="STATUTORY_TAX_RATE", value=Decimal("0.05"), effective_from=date(2026, 1, 1)
        )
        await repo.create(
            key="STATUTORY_TAX_RATE", value=Decimal("0.07"), effective_from=date(2026, 1, 1)
        )
        await session.commit()

    with pytest.raises(AmbiguousEffectiveStateError):
        await service.get_value("STATUTORY_TAX_RATE", date(2026, 3, 1))


async def test_update_only_changes_description(service: PayrollStatutoryParameterService):
    parameter = await service.create(_create())

    updated = await service.update(
        parameter.id, PayrollStatutoryParameterUpdate(description="Updated")
    )

    assert updated is not None
    assert updated.description == "Updated"
    assert updated.value == parameter.value


async def test_list_returns_created(service: PayrollStatutoryParameterService):
    await service.create(_create(key="STATUTORY_TAX_RATE"))
    await service.create(_create(key="OVERTIME_MULTIPLIER_WEEKDAY"))

    items = await service.list()

    assert {"STATUTORY_TAX_RATE", "OVERTIME_MULTIPLIER_WEEKDAY"}.issubset(
        {item.key for item in items}
    )


async def test_get_missing_returns_none(service: PayrollStatutoryParameterService):
    assert await service.get(uuid.uuid4()) is None
