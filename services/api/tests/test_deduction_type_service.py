import uuid
from collections.abc import AsyncGenerator, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.schemas.deduction_type import DeductionTypeCreate, DeductionTypeUpdate
from eop_api.services.deduction_type import DeductionTypeService, DuplicateDeductionTypeCodeError
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
            await conn.execute(text("TRUNCATE TABLE deduction_types CASCADE"))
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> DeductionTypeService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return DeductionTypeService(uow_factory)


async def test_create_and_get(service: DeductionTypeService):
    deduction_type = await service.create(DeductionTypeCreate(code="LOAN", name="Loan Repayment"))

    fetched = await service.get(deduction_type.id)

    assert fetched is not None
    assert fetched.code == "LOAN"
    assert fetched.name == "Loan Repayment"


async def test_create_rejects_duplicate_code(service: DeductionTypeService):
    await service.create(DeductionTypeCreate(code="LOAN", name="Loan Repayment"))

    with pytest.raises(DuplicateDeductionTypeCodeError):
        await service.create(DeductionTypeCreate(code="LOAN", name="Other"))


async def test_list_returns_created(service: DeductionTypeService):
    await service.create(DeductionTypeCreate(code="LOAN", name="Loan Repayment"))
    await service.create(DeductionTypeCreate(code="INSURANCE", name="Insurance Premium"))

    items = await service.list()

    assert {"LOAN", "INSURANCE"}.issubset({item.code for item in items})


async def test_update_existing(service: DeductionTypeService):
    deduction_type = await service.create(DeductionTypeCreate(code="LOAN", name="Before"))

    updated = await service.update(deduction_type.id, DeductionTypeUpdate(name="After"))

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(service: DeductionTypeService):
    assert await service.update(uuid.uuid4(), DeductionTypeUpdate(name="After")) is None


async def test_delete_existing(service: DeductionTypeService):
    deduction_type = await service.create(DeductionTypeCreate(code="LOAN", name="To Delete"))

    deleted = await service.delete(deduction_type.id)

    assert deleted is True
    assert await service.get(deduction_type.id) is None


async def test_get_missing_returns_none(service: DeductionTypeService):
    assert await service.get(uuid.uuid4()) is None
