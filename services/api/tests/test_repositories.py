import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.core.config import settings
from eop_api.db.base import BaseEntity
from eop_api.repositories import BaseRepository

pytestmark = pytest.mark.anyio


class _Widget(BaseEntity):
    """Test-only model used to exercise BaseRepository against a real table."""

    __tablename__ = "test_repository_widgets"

    name: Mapped[str] = mapped_column()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession]:
    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        await conn.run_sync(_Widget.metadata.create_all, tables=[_Widget.__table__])

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as db_session:
            yield db_session
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(_Widget.metadata.drop_all, tables=[_Widget.__table__])
        await engine.dispose()


@pytest.fixture
def repo(session: AsyncSession) -> BaseRepository[_Widget]:
    return BaseRepository(session, _Widget)


async def test_create_and_get(repo: BaseRepository[_Widget]):
    widget = await repo.create(name="alpha")

    fetched = await repo.get(widget.id)

    assert fetched is not None
    assert fetched.name == "alpha"


async def test_get_missing_returns_none(repo: BaseRepository[_Widget]):
    assert await repo.get(uuid.uuid4()) is None


async def test_list_returns_all(repo: BaseRepository[_Widget]):
    await repo.create(name="a")
    await repo.create(name="b")

    items = await repo.list()

    assert {item.name for item in items} == {"a", "b"}


async def test_update_existing(repo: BaseRepository[_Widget]):
    widget = await repo.create(name="before")

    updated = await repo.update(widget.id, name="after")

    assert updated is not None
    assert updated.name == "after"


async def test_update_missing_returns_none(repo: BaseRepository[_Widget]):
    assert await repo.update(uuid.uuid4(), name="after") is None


async def test_delete_existing(repo: BaseRepository[_Widget]):
    widget = await repo.create(name="to-delete")

    deleted = await repo.delete(widget.id)

    assert deleted is True
    assert await repo.get(widget.id) is None


async def test_delete_missing_returns_false(repo: BaseRepository[_Widget]):
    assert await repo.delete(uuid.uuid4()) is False


async def test_exists(repo: BaseRepository[_Widget]):
    widget = await repo.create(name="exists")

    assert await repo.exists(widget.id) is True
    assert await repo.exists(uuid.uuid4()) is False


async def test_count(repo: BaseRepository[_Widget]):
    await repo.create(name="a")
    await repo.create(name="b")
    await repo.create(name="c")

    assert await repo.count() == 3


async def test_paginate(repo: BaseRepository[_Widget]):
    for i in range(5):
        await repo.create(name=f"item-{i}")

    page = await repo.paginate(offset=1, limit=2)

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2
