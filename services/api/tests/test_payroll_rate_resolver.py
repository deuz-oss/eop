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
from eop_api.models.compensation import Compensation
from eop_api.schemas.payroll_statutory_parameter import PayrollStatutoryParameterCreate
from eop_api.services.payroll.rate_resolver import PayrollRateResolver
from eop_api.services.payroll_statutory_parameter import (
    MissingStatutoryParameterError,
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
def parameter_service(
    session_factory: Callable[[], AsyncSession],
) -> PayrollStatutoryParameterService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return PayrollStatutoryParameterService(uow_factory)


@pytest.fixture
def resolver(parameter_service: PayrollStatutoryParameterService) -> PayrollRateResolver:
    return PayrollRateResolver(parameter_service)


def _compensation(amount: Decimal = Decimal("4400000.00")) -> Compensation:
    """An in-memory, unpersisted `Compensation` -- `PayrollRateResolver`
    only reads `base_salary_amount`/`base_salary_currency`, so no database
    row or HrEmployee scaffolding is needed."""
    return Compensation(
        id=uuid.uuid4(),
        employee_id=uuid.uuid4(),
        base_salary_amount=amount,
        base_salary_currency="IDR",
        effective_from=date(2026, 1, 1),
        is_active=True,
    )


async def test_daily_rate_divides_base_salary_by_working_days(
    resolver: PayrollRateResolver, parameter_service: PayrollStatutoryParameterService
):
    await parameter_service.create(
        PayrollStatutoryParameterCreate(
            key="STANDARD_WORKING_DAYS_PER_MONTH",
            value=Decimal("22"),
            effective_from=date(2026, 1, 1),
        )
    )

    daily = await resolver.daily_rate(_compensation(), date(2026, 1, 31))

    assert daily.amount == Decimal("200000.00")
    assert daily.currency == "IDR"


async def test_hourly_rate_divides_daily_rate_by_standard_hours(
    resolver: PayrollRateResolver, parameter_service: PayrollStatutoryParameterService
):
    await parameter_service.create(
        PayrollStatutoryParameterCreate(
            key="STANDARD_WORKING_DAYS_PER_MONTH",
            value=Decimal("22"),
            effective_from=date(2026, 1, 1),
        )
    )
    await parameter_service.create(
        PayrollStatutoryParameterCreate(
            key="STANDARD_DAILY_HOURS", value=Decimal("8"), effective_from=date(2026, 1, 1)
        )
    )

    hourly = await resolver.hourly_rate(_compensation(), date(2026, 1, 31))

    assert hourly.amount == Decimal("25000.00")


async def test_daily_rate_raises_when_working_days_not_configured(
    resolver: PayrollRateResolver,
):
    with pytest.raises(MissingStatutoryParameterError):
        await resolver.daily_rate(_compensation(), date(2026, 1, 31))
