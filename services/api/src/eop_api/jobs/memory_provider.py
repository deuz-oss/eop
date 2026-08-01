import threading
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from eop_api.jobs.base import JobProvider
from eop_api.schemas.job import Job


class InMemoryJobProvider(JobProvider):
    """Development/testing `JobProvider` that keeps queued jobs in a list.

    There is no worker, scheduler, or poller behind this -- `enqueue_in` and
    `enqueue_at` accept scheduling parameters to satisfy the `JobProvider`
    interface, but nothing in this class ever executes a job or acts on that
    scheduling; it only records that one was queued, at the time it was
    queued. Real delayed execution is the responsibility of a future
    queue-backed provider.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: list[Job] = []

    @property
    def jobs(self) -> list[Job]:
        """Snapshot of every job queued so far, in enqueue order."""
        with self._lock:
            return list(self._jobs)

    async def enqueue(self, *, name: str, payload: Mapping[str, Any] | None = None) -> Job:
        return self._store(name=name, payload=payload)

    async def enqueue_in(
        self, *, delay: timedelta, name: str, payload: Mapping[str, Any] | None = None
    ) -> Job:
        return self._store(name=name, payload=payload)

    async def enqueue_at(
        self, *, run_at: datetime, name: str, payload: Mapping[str, Any] | None = None
    ) -> Job:
        return self._store(name=name, payload=payload)

    def _store(self, *, name: str, payload: Mapping[str, Any] | None) -> Job:
        # Copy into a plain dict we own -- the caller's mapping is never
        # mutated, and mutations to the caller's mapping after this call
        # never leak into the stored job.
        stored_payload = dict(payload) if payload is not None else {}
        job = Job(
            id=uuid.uuid4(),
            name=name,
            payload=stored_payload,
            queued_at=datetime.now(UTC),
        )
        with self._lock:
            self._jobs.append(job)
        return job
