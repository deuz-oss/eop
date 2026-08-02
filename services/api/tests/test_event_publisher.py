from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from eop_api.events.memory_publisher import InMemoryEventPublisher
from eop_api.schemas.event import EventRequest

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def publisher() -> InMemoryEventPublisher:
    return InMemoryEventPublisher()


async def test_publish_stores_event_with_name_and_payload(publisher: InMemoryEventPublisher):
    event = await publisher.publish(name="employee.created", payload={"employee_id": "abc"})

    assert event.name == "employee.created"
    assert event.payload == {"employee_id": "abc"}
    assert event.id is not None


async def test_publish_without_payload_defaults_to_empty_dict(publisher: InMemoryEventPublisher):
    event = await publisher.publish(name="ping")

    assert event.payload == {}


async def test_publish_sets_occurred_at_close_to_now(publisher: InMemoryEventPublisher):
    before = datetime.now(UTC)

    event = await publisher.publish(name="ping")

    after = datetime.now(UTC)
    assert before <= event.occurred_at <= after


async def test_publish_many_stores_all_events_in_order(publisher: InMemoryEventPublisher):
    requests = [
        EventRequest(name="a", payload={"seq": 1}),
        EventRequest(name="b", payload={"seq": 2}),
    ]

    events = await publisher.publish_many(requests)

    assert [e.name for e in events] == ["a", "b"]
    assert events == publisher.events


async def test_each_publish_produces_a_unique_id(publisher: InMemoryEventPublisher):
    first = await publisher.publish(name="event")
    second = await publisher.publish(name="event")

    assert first.id != second.id


async def test_events_are_stored_in_publish_order(publisher: InMemoryEventPublisher):
    await publisher.publish(name="first")
    await publisher.publish_many([EventRequest(name="second")])
    await publisher.publish(name="third")

    names = [e.name for e in publisher.events]
    assert names == ["first", "second", "third"]


async def test_events_property_returns_a_snapshot(publisher: InMemoryEventPublisher):
    await publisher.publish(name="first")

    snapshot = publisher.events
    snapshot.clear()

    assert [e.name for e in publisher.events] == ["first"]


async def test_event_is_immutable(publisher: InMemoryEventPublisher):
    event = await publisher.publish(name="event")

    with pytest.raises(ValidationError):
        event.name = "changed"


async def test_publish_does_not_mutate_the_caller_supplied_payload(
    publisher: InMemoryEventPublisher,
):
    original_payload = {"count": 1}

    event = await publisher.publish(name="event", payload=original_payload)

    assert original_payload == {"count": 1}
    assert event.payload is not original_payload


async def test_mutating_the_caller_supplied_payload_after_publish_does_not_leak_into_the_event(
    publisher: InMemoryEventPublisher,
):
    original_payload = {"count": 1}

    event = await publisher.publish(name="event", payload=original_payload)
    original_payload["count"] = 2

    assert event.payload == {"count": 1}
