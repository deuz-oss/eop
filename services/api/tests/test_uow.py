from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.core.config import settings
from eop_api.db.base import BaseEntity
from eop_api.repositories import BaseRepository
from eop_api.uow import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _FakeAsyncSession:
    """Minimal stand-in for AsyncSession that records lifecycle calls."""

    def __init__(self) -> None:
        self.commit_count = 0
        self.rollback_count = 0
        self.close_count = 0

    async def commit(self) -> None:
        self.commit_count += 1

    async def rollback(self) -> None:
        self.rollback_count += 1

    async def close(self) -> None:
        self.close_count += 1


class _RaisingError(Exception):
    pass


def _factory(session: _FakeAsyncSession):
    return lambda: session


async def test_commit_persists_and_closes():
    session = _FakeAsyncSession()

    async with SQLAlchemyUnitOfWork(_factory(session)) as uow:
        await uow.commit()

    assert session.commit_count == 1
    assert session.close_count == 1
    assert session.rollback_count == 1  # safety-net rollback after commit is a no-op on the DB


async def test_rollback_on_exception():
    session = _FakeAsyncSession()

    with pytest.raises(_RaisingError):
        async with SQLAlchemyUnitOfWork(_factory(session)) as uow:
            assert uow.session is session
            raise _RaisingError("boom")

    assert session.commit_count == 0
    assert session.rollback_count == 1
    assert session.close_count == 1


async def test_no_explicit_commit_rolls_back():
    session = _FakeAsyncSession()

    async with SQLAlchemyUnitOfWork(_factory(session)):
        pass

    assert session.commit_count == 0
    assert session.rollback_count == 1
    assert session.close_count == 1


async def test_session_closed_on_exit():
    session = _FakeAsyncSession()

    async with SQLAlchemyUnitOfWork(_factory(session)) as uow:
        assert session.close_count == 0
        await uow.commit()

    assert session.close_count == 1

    with pytest.raises(RuntimeError):
        _ = uow.session


async def test_session_accessed_outside_context_raises():
    uow = SQLAlchemyUnitOfWork(_factory(_FakeAsyncSession()))

    with pytest.raises(RuntimeError):
        _ = uow.session


async def test_shared_session_within_context():
    session = _FakeAsyncSession()

    async with SQLAlchemyUnitOfWork(_factory(session)) as uow:
        first = uow.session
        second = uow.session

    assert first is session
    assert second is session
    assert first is second


class _Order(BaseEntity):
    """Test-only model used to exercise SQLAlchemyUnitOfWork against a real table."""

    __tablename__ = "test_uow_orders"

    reference: Mapped[str] = mapped_column()


@pytest.fixture
async def session_factory() -> AsyncGenerator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        await conn.run_sync(_Order.metadata.create_all, tables=[_Order.__table__])

    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(_Order.metadata.drop_all, tables=[_Order.__table__])
        await engine.dispose()


async def test_commit_persists_across_sessions(
    session_factory: async_sessionmaker[AsyncSession],
):
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        repo = BaseRepository(uow.session, _Order)
        order = await repo.create(reference="ORD-1")
        await uow.commit()
        order_id = order.id

    async with session_factory() as verify_session:
        verify_repo = BaseRepository(verify_session, _Order)
        assert await verify_repo.get(order_id) is not None


async def test_rollback_on_exception_does_not_persist(
    session_factory: async_sessionmaker[AsyncSession],
):
    order_id = None

    with pytest.raises(_RaisingError):
        async with SQLAlchemyUnitOfWork(session_factory) as uow:
            repo = BaseRepository(uow.session, _Order)
            order = await repo.create(reference="ORD-2")
            order_id = order.id
            raise _RaisingError("boom")

    async with session_factory() as verify_session:
        verify_repo = BaseRepository(verify_session, _Order)
        assert await verify_repo.get(order_id) is None


async def test_shared_session_across_repositories(
    session_factory: async_sessionmaker[AsyncSession],
):
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        write_repo = BaseRepository(uow.session, _Order)
        read_repo = BaseRepository(uow.session, _Order)

        assert write_repo.session is read_repo.session is uow.session

        order = await write_repo.create(reference="ORD-3")

        # Visible to a second repository sharing the same uncommitted session.
        assert await read_repo.get(order.id) is not None
