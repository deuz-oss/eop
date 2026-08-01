import abc
from types import TracebackType
from typing import Self


class AbstractUnitOfWork(abc.ABC):
    """Owns the transaction boundary for a logical unit of work.

    Repositories operate against the session/connection a concrete
    implementation exposes but must never commit, rollback, or close it
    themselves. Callers must explicitly call `commit()` to persist changes;
    exiting the context without an explicit commit rolls the transaction
    back, and the session is always closed on exit.
    """

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            await self.rollback()
        finally:
            await self.close()

    @abc.abstractmethod
    async def commit(self) -> None: ...

    @abc.abstractmethod
    async def rollback(self) -> None: ...

    @abc.abstractmethod
    async def close(self) -> None: ...
