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
from eop_api.repositories.file import FileRepository

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def connection() -> AsyncGenerator[AsyncConnection]:
    """A single connection with its own transaction, rolled back after the test.

    The tables are real, migration-managed tables shared with the running
    application, so tests must never commit or drop them. Everything a test does
    happens inside one uncommitted transaction that is discarded on teardown.
    """
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
def repo(session: AsyncSession) -> FileRepository:
    return FileRepository(session)


def _file_kwargs(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "filename": "report.pdf",
        "content_type": "application/pdf",
        "size": 1024,
        "storage_key": str(uuid.uuid4()),
        "bucket": "eop-files",
    }
    values.update(overrides)
    return values


async def test_create_and_get(repo: FileRepository):
    file_object = await repo.create(**_file_kwargs())

    fetched = await repo.get(file_object.id)

    assert fetched is not None
    assert fetched.filename == "report.pdf"
    assert fetched.content_type == "application/pdf"
    assert fetched.size == 1024
    assert fetched.bucket == "eop-files"
    assert fetched.storage_key == file_object.storage_key
    assert fetched.created_at is not None


async def test_get_missing_returns_none(repo: FileRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_delete_existing(repo: FileRepository):
    file_object = await repo.create(**_file_kwargs())

    deleted = await repo.delete(file_object.id)

    assert deleted is True
    assert await repo.get(file_object.id) is None


async def test_delete_missing_returns_false(repo: FileRepository):
    assert await repo.delete(uuid.uuid4()) is False
