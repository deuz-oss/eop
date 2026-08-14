import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from eop_api.jobs.base import JobProvider
from eop_api.jobs.memory_provider import InMemoryJobProvider
from eop_api.schemas.job import Job
from eop_api.services.job import JobService, get_default_job_provider

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeJobProvider(JobProvider):
    """Records exactly which `JobProvider` method `JobService` delegated to."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def enqueue(self, *, name: str, payload: Mapping[str, Any] | None = None) -> Job:
        self.calls.append(("enqueue", {"name": name, "payload": payload}))
        return _make_job(name, payload)

    async def enqueue_in(
        self, *, delay: timedelta, name: str, payload: Mapping[str, Any] | None = None
    ) -> Job:
        self.calls.append(("enqueue_in", {"delay": delay, "name": name, "payload": payload}))
        return _make_job(name, payload)

    async def enqueue_at(
        self, *, run_at: datetime, name: str, payload: Mapping[str, Any] | None = None
    ) -> Job:
        self.calls.append(("enqueue_at", {"run_at": run_at, "name": name, "payload": payload}))
        return _make_job(name, payload)


def _make_job(name: str, payload: Mapping[str, Any] | None) -> Job:
    return Job(id=uuid.uuid4(), name=name, payload=dict(payload or {}), queued_at=datetime.now(UTC))


@pytest.fixture
def provider() -> FakeJobProvider:
    return FakeJobProvider()


@pytest.fixture
def service(provider: FakeJobProvider) -> JobService:
    return JobService(provider)


async def test_enqueue_delegates_to_provider(service: JobService, provider: FakeJobProvider):
    job = await service.enqueue(name="send_email", payload={"to": "a@example.com"})

    assert provider.calls == [
        ("enqueue", {"name": "send_email", "payload": {"to": "a@example.com"}})
    ]
    assert job.name == "send_email"
    assert job.payload == {"to": "a@example.com"}


async def test_enqueue_in_delegates_to_provider(service: JobService, provider: FakeJobProvider):
    delay = timedelta(minutes=10)

    job = await service.enqueue_in(delay=delay, name="reminder", payload={"foo": "bar"})

    assert provider.calls == [
        ("enqueue_in", {"delay": delay, "name": "reminder", "payload": {"foo": "bar"}})
    ]
    assert job.name == "reminder"


async def test_enqueue_at_delegates_to_provider(service: JobService, provider: FakeJobProvider):
    run_at = datetime.now(UTC) + timedelta(days=1)

    job = await service.enqueue_at(run_at=run_at, name="report", payload=None)

    assert provider.calls == [("enqueue_at", {"run_at": run_at, "name": "report", "payload": None})]
    assert job.name == "report"


async def test_service_performs_no_business_logic_of_its_own(
    service: JobService, provider: FakeJobProvider
):
    """The service is a pure pass-through: whatever the provider returns is
    exactly what callers get back, unmodified."""
    job = await service.enqueue(name="anything")

    assert job.id is not None
    assert len(provider.calls) == 1


async def test_default_provider_is_shared_across_service_instances():
    """Two `JobService`s created without an explicit provider must delegate
    to the same underlying `InMemoryJobProvider`, since job storage is only
    ever in-process memory -- a fresh provider per service would silently
    lose every previously queued job."""
    first_service = JobService()
    second_service = JobService()

    job = await first_service.enqueue(name="shared-provider-check")

    default_provider = get_default_job_provider()
    assert isinstance(default_provider, InMemoryJobProvider)
    assert job in default_provider.jobs
    assert second_service is not first_service
