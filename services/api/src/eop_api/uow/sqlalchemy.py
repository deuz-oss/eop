from collections.abc import Callable
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession

from eop_api.db.session import AsyncSessionLocal
from eop_api.uow.base import AbstractUnitOfWork


class SQLAlchemyUnitOfWork(AbstractUnitOfWork):
    """Unit of work backed by a single SQLAlchemy `AsyncSession`.

    Opens a new session on `__aenter__` and exposes it via `.session` so
    that repositories constructed within the context share one connection
    and transaction. Always closes the session on exit.
    """

    def __init__(self, session_factory: Callable[[], AsyncSession] = AsyncSessionLocal) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        return await super().__aenter__()

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("Unit of work session accessed outside of an active context")
        return self._session

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        if self._session is None:
            return
        await self._session.rollback()

    async def close(self) -> None:
        if self._session is None:
            return
        await self._session.close()
        self._session = None
