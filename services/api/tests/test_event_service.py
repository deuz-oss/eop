import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import pytest

from eop_api.events.base import EventPublisher
from eop_api.events.memory_publisher import InMemoryEventPublisher
from eop_api.schemas.event import Event, EventRequest
from eop_api.services.event import EventService, get_default_event_publisher

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeEventPublisher(EventPublisher):
    """Records exactly which `EventPublisher` method `EventService` delegated to."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    async def publish(self, *, name: str, payload: Mapping[str, Any] | None = None) -> Event:
        self.calls.append(("publish", {"name": name, "payload": payload}))
        return _make_event(name, payload)

    async def publish_many(self, events: Sequence[EventRequest]) -> list[Event]:
        self.calls.append(("publish_many", events))
        return [_make_event(request.name, request.payload) for request in events]


def _make_event(name: str, payload: Mapping[str, Any] | None) -> Event:
    return Event(
        id=uuid.uuid4(),
        name=name,
        payload=dict(payload or {}),
        occurred_at=datetime.now(UTC),
    )


@pytest.fixture
def publisher() -> FakeEventPublisher:
    return FakeEventPublisher()


@pytest.fixture
def service(publisher: FakeEventPublisher) -> EventService:
    return EventService(publisher)


async def test_publish_delegates_to_publisher(service: EventService, publisher: FakeEventPublisher):
    event = await service.publish(name="employee.created", payload={"employee_id": "abc"})

    assert publisher.calls == [
        ("publish", {"name": "employee.created", "payload": {"employee_id": "abc"}})
    ]
    assert event.name == "employee.created"
    assert event.payload == {"employee_id": "abc"}


async def test_publish_many_delegates_to_publisher(
    service: EventService, publisher: FakeEventPublisher
):
    requests = [
        EventRequest(name="a", payload={"seq": 1}),
        EventRequest(name="b", payload={"seq": 2}),
    ]

    events = await service.publish_many(requests)

    assert publisher.calls == [("publish_many", requests)]
    assert [e.name for e in events] == ["a", "b"]


async def test_service_performs_no_business_logic_of_its_own(
    service: EventService, publisher: FakeEventPublisher
):
    """The service is a pure pass-through: whatever the publisher returns is
    exactly what callers get back, unmodified."""
    event = await service.publish(name="anything")

    assert event.id is not None
    assert len(publisher.calls) == 1


async def test_default_publisher_is_shared_across_service_instances():
    """Two `EventService`s created without an explicit publisher must
    delegate to the same underlying `InMemoryEventPublisher`, since event
    storage is only ever in-process memory -- a fresh publisher per service
    would silently lose every previously published event."""
    first_service = EventService()
    second_service = EventService()

    event = await first_service.publish(name="shared-publisher-check")

    default_publisher = get_default_event_publisher()
    assert isinstance(default_publisher, InMemoryEventPublisher)
    assert event in default_publisher.events
    assert second_service is not first_service
