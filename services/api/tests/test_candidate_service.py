import uuid
from collections.abc import AsyncGenerator, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.schemas.candidate import CandidateCreate, CandidateUpdate
from eop_api.schemas.pagination import PaginationParams
from eop_api.schemas.search import SearchParams
from eop_api.services.candidate import CandidateService, DuplicateCandidateEmailError
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
            await conn.execute(text("TRUNCATE TABLE candidates CASCADE"))
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> CandidateService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return CandidateService(uow_factory)


def _create(email: str = "ada@example.com", **overrides) -> CandidateCreate:
    values = {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "full_name": "Ada Lovelace",
        "email": email,
    }
    values.update(overrides)
    return CandidateCreate(**values)


async def test_create_and_get(service: CandidateService):
    candidate = await service.create(_create())

    fetched = await service.get(candidate.id)

    assert fetched is not None
    assert fetched.full_name == "Ada Lovelace"
    assert fetched.email == "ada@example.com"


async def test_create_rejects_duplicate_email(service: CandidateService):
    await service.create(_create(email="ada@example.com"))

    with pytest.raises(DuplicateCandidateEmailError):
        await service.create(_create(email="ada@example.com", full_name="Ada Two"))


async def test_get_missing_returns_none(service: CandidateService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(service: CandidateService):
    await service.create(_create(email="ada@example.com"))
    await service.create(_create(email="alan@example.com", full_name="Alan Turing"))

    items = await service.list()

    assert {"Ada Lovelace", "Alan Turing"}.issubset({item.full_name for item in items})


async def test_update_existing(service: CandidateService):
    candidate = await service.create(_create())

    updated = await service.update(candidate.id, CandidateUpdate(full_name="After"))

    assert updated is not None
    assert updated.full_name == "After"


async def test_update_missing_returns_none(service: CandidateService):
    assert await service.update(uuid.uuid4(), CandidateUpdate(full_name="After")) is None


async def test_update_rejects_duplicate_email(service: CandidateService):
    await service.create(_create(email="ada@example.com"))
    other = await service.create(_create(email="alan@example.com", full_name="Alan Turing"))

    with pytest.raises(DuplicateCandidateEmailError):
        await service.update(other.id, CandidateUpdate(email="ada@example.com"))


async def test_update_allows_unchanged_email(service: CandidateService):
    candidate = await service.create(_create(email="ada@example.com"))

    updated = await service.update(
        candidate.id, CandidateUpdate(email="ada@example.com", full_name="Ada Renamed")
    )

    assert updated is not None
    assert updated.full_name == "Ada Renamed"


async def test_delete_existing(service: CandidateService):
    candidate = await service.create(_create())

    deleted = await service.delete(candidate.id)

    assert deleted is True
    assert await service.get(candidate.id) is None


async def test_delete_missing_returns_false(service: CandidateService):
    assert await service.delete(uuid.uuid4()) is False


async def test_list_paginated_passes_through_search(service: CandidateService):
    await service.create(_create(email="ada@example.com"))
    await service.create(_create(email="alan@example.com", full_name="Alan Turing"))

    page = await service.list_paginated(PaginationParams(offset=0, limit=50), SearchParams(q="ada"))

    assert page.total == 1
    assert page.items[0].full_name == "Ada Lovelace"
