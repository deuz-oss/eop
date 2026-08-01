from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from eop_api.jobs.base import JobProvider
from eop_api.jobs.memory_provider import InMemoryJobProvider
from eop_api.schemas.job import Job

_default_provider = InMemoryJobProvider()


def get_default_job_provider() -> JobProvider:
    """The process-wide default `JobProvider`.

    Every `JobService()` created without an explicit provider shares this
    same in-memory queue. Swapping in a future queue-backed provider means
    changing this factory, not any caller.
    """
    return _default_provider


class JobService:
    """Entry point for enqueuing background jobs. Owns no execution logic.

    Delegates everything to a `JobProvider`; business modules should depend
    on this service, never on a concrete provider. Nothing in this PR calls
    it yet -- it is infrastructure for later adoption.
    """

    def __init__(self, provider: JobProvider | None = None) -> None:
        self._provider = provider or get_default_job_provider()

    async def enqueue(self, *, name: str, payload: Mapping[str, Any] | None = None) -> Job:
        return await self._provider.enqueue(name=name, payload=payload)

    async def enqueue_in(
        self, *, delay: timedelta, name: str, payload: Mapping[str, Any] | None = None
    ) -> Job:
        return await self._provider.enqueue_in(delay=delay, name=name, payload=payload)

    async def enqueue_at(
        self, *, run_at: datetime, name: str, payload: Mapping[str, Any] | None = None
    ) -> Job:
        return await self._provider.enqueue_at(run_at=run_at, name=name, payload=payload)
