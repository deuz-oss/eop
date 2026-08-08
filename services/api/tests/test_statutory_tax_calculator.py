from collections.abc import AsyncGenerator, Callable
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.foundation.monetary.types import Money
from eop_api.schemas.payroll_statutory_parameter import PayrollStatutoryParameterCreate
from eop_api.services.payroll.statutory_tax_calculator import StatutoryTaxCalculator
from eop_api.services.payroll_statutory_parameter import PayrollStatutoryParameterService
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
def parameter_service(
    session_factory: Callable[[], AsyncSession],
) -> PayrollStatutoryParameterService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return PayrollStatutoryParameterService(uow_factory)


@pytest.fixture
def calculator(parameter_service: PayrollStatutoryParameterService) -> StatutoryTaxCalculator:
    return StatutoryTaxCalculator(parameter_service)


async def test_compute_returns_none_when_unconfigured(calculator: StatutoryTaxCalculator):
    result = await calculator.compute(Money(Decimal("5000000.00"), "IDR"), date(2026, 1, 31))

    assert result is None


async def test_compute_applies_configured_rate(
    calculator: StatutoryTaxCalculator, parameter_service: PayrollStatutoryParameterService
):
    await parameter_service.create(
        PayrollStatutoryParameterCreate(
            key="STATUTORY_TAX_RATE", value=Decimal("0.05"), effective_from=date(2026, 1, 1)
        )
    )

    result = await calculator.compute(Money(Decimal("5000000.00"), "IDR"), date(2026, 1, 31))

    assert result is not None
    assert result.line_amount == Decimal("250000.00")
    assert result.component_type == "STATUTORY_DEDUCTION"


async def test_compute_returns_none_when_rate_is_zero(
    calculator: StatutoryTaxCalculator, parameter_service: PayrollStatutoryParameterService
):
    await parameter_service.create(
        PayrollStatutoryParameterCreate(
            key="STATUTORY_TAX_RATE", value=Decimal("0"), effective_from=date(2026, 1, 1)
        )
    )

    result = await calculator.compute(Money(Decimal("5000000.00"), "IDR"), date(2026, 1, 31))

    assert result is None
