from datetime import UTC, datetime, timedelta

import pytest

from eop_api.jobs.memory_provider import InMemoryJobProvider

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def provider() -> InMemoryJobProvider:
    return InMemoryJobProvider()


async def test_enqueue_stores_job_with_name_and_payload(provider: InMemoryJobProvider):
    job = await provider.enqueue(name="send_welcome_email", payload={"user_id": "abc"})

    assert job.name == "send_welcome_email"
    assert job.payload == {"user_id": "abc"}
    assert job.id is not None


async def test_enqueue_without_payload_defaults_to_empty_dict(provider: InMemoryJobProvider):
    job = await provider.enqueue(name="cleanup")

    assert job.payload == {}


async def test_enqueue_sets_queued_at_close_to_now(provider: InMemoryJobProvider):
    before = datetime.now(UTC)

    job = await provider.enqueue(name="cleanup")

    after = datetime.now(UTC)
    assert before <= job.queued_at <= after


async def test_enqueue_in_stores_job(provider: InMemoryJobProvider):
    job = await provider.enqueue_in(
        delay=timedelta(minutes=5), name="reminder", payload={"foo": "bar"}
    )

    assert job.name == "reminder"
    assert job.payload == {"foo": "bar"}
    assert job in provider.jobs


async def test_enqueue_at_stores_job(provider: InMemoryJobProvider):
    run_at = datetime.now(UTC) + timedelta(hours=1)

    job = await provider.enqueue_at(run_at=run_at, name="report", payload={"format": "pdf"})

    assert job.name == "report"
    assert job.payload == {"format": "pdf"}
    assert job in provider.jobs


async def test_each_enqueue_produces_a_unique_id(provider: InMemoryJobProvider):
    first = await provider.enqueue(name="job")
    second = await provider.enqueue(name="job")

    assert first.id != second.id


async def test_jobs_are_stored_in_enqueue_order(provider: InMemoryJobProvider):
    await provider.enqueue(name="first")
    await provider.enqueue_in(delay=timedelta(seconds=1), name="second")
    await provider.enqueue_at(run_at=datetime.now(UTC), name="third")

    names = [job.name for job in provider.jobs]
    assert names == ["first", "second", "third"]


async def test_jobs_property_returns_a_snapshot(provider: InMemoryJobProvider):
    await provider.enqueue(name="first")

    snapshot = provider.jobs
    snapshot.clear()

    assert [job.name for job in provider.jobs] == ["first"]


async def test_enqueue_does_not_mutate_the_caller_supplied_payload(
    provider: InMemoryJobProvider,
):
    original_payload = {"count": 1}

    job = await provider.enqueue(name="job", payload=original_payload)

    assert original_payload == {"count": 1}
    assert job.payload is not original_payload


async def test_mutating_the_caller_supplied_payload_after_enqueue_does_not_leak_into_the_job(
    provider: InMemoryJobProvider,
):
    original_payload = {"count": 1}

    job = await provider.enqueue(name="job", payload=original_payload)
    original_payload["count"] = 2

    assert job.payload == {"count": 1}
