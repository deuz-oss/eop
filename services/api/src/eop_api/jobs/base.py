import abc
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from eop_api.schemas.job import Job


class JobProvider(abc.ABC):
    """Reusable abstraction over a background job queue.

    Business modules must never talk to a concrete queue implementation
    (e.g. Redis, Celery) directly -- everything goes through this interface
    via `JobService`. Generic enough that a future queue-backed provider can
    replace `InMemoryJobProvider` without callers changing.

    `payload` is accepted as a `Mapping` so callers know a provider will
    never mutate what they pass in.
    """

    @abc.abstractmethod
    async def enqueue(self, *, name: str, payload: Mapping[str, Any] | None = None) -> Job:
        """Queue `name` for immediate processing with `payload`."""
        ...

    @abc.abstractmethod
    async def enqueue_in(
        self, *, delay: timedelta, name: str, payload: Mapping[str, Any] | None = None
    ) -> Job:
        """Queue `name` to become eligible for processing after `delay`."""
        ...

    @abc.abstractmethod
    async def enqueue_at(
        self, *, run_at: datetime, name: str, payload: Mapping[str, Any] | None = None
    ) -> Job:
        """Queue `name` to become eligible for processing at `run_at`."""
        ...
