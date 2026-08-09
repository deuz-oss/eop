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
from eop_api.repositories.candidate import CandidateRepository
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
def repo(session: AsyncSession) -> CandidateRepository:
    return CandidateRepository(session)


async def test_create_and_get(repo: CandidateRepository):
    candidate = await repo.create(
        first_name="Ada", last_name="Lovelace", full_name="Ada Lovelace", email="ada@example.com"
    )

    fetched = await repo.get(candidate.id)

    assert fetched is not None
    assert fetched.full_name == "Ada Lovelace"
    assert fetched.email == "ada@example.com"
    assert fetched.phone is None


async def test_get_missing_returns_none(repo: CandidateRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_get_by_email(repo: CandidateRepository):
    candidate = await repo.create(
        first_name="Ada", last_name="Lovelace", full_name="Ada Lovelace", email="ada@example.com"
    )

    found = await repo.get_by_email("ada@example.com")

    assert found is not None
    assert found.id == candidate.id
    assert await repo.get_by_email("missing@example.com") is None


async def test_update_existing(repo: CandidateRepository):
    candidate = await repo.create(
        first_name="Ada", last_name="Lovelace", full_name="Before", email="ada@example.com"
    )

    updated = await repo.update(candidate.id, full_name="After")

    assert updated is not None
    assert updated.full_name == "After"


async def test_delete_existing(repo: CandidateRepository):
    candidate = await repo.create(
        first_name="Ada", last_name="Lovelace", full_name="Ada Lovelace", email="ada@example.com"
    )

    deleted = await repo.delete(candidate.id)

    assert deleted is True
    assert await repo.get(candidate.id) is None


async def test_paginate_search_by_name(repo: CandidateRepository):
    await repo.create(
        first_name="Ada", last_name="Lovelace", full_name="Ada Lovelace", email="ada@example.com"
    )
    await repo.create(
        first_name="Alan", last_name="Turing", full_name="Alan Turing", email="alan@example.com"
    )

    page = await repo.paginate(search=SearchParams(q="ada"))

    assert page.total == 1
    assert page.items[0].full_name == "Ada Lovelace"
