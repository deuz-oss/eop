from collections.abc import Mapping, Sequence
from typing import Any

from eop_api.events.base import EventPublisher
from eop_api.events.memory_publisher import InMemoryEventPublisher
from eop_api.schemas.event import Event, EventRequest

_default_publisher = InMemoryEventPublisher()


def get_default_event_publisher() -> EventPublisher:
    """The process-wide default `EventPublisher`.

    Every `EventService()` created without an explicit publisher shares this
    same in-memory store. Swapping in a future broker-backed publisher means
    changing this factory, not any caller.
    """
    return _default_publisher


class EventService:
    """Entry point for publishing events. Owns no business logic.

    Delegates everything to an `EventPublisher`; business modules should
    depend on this service, never on a concrete publisher. Nothing in this
    PR calls it yet -- it is infrastructure for later adoption.
    """

    def __init__(self, publisher: EventPublisher | None = None) -> None:
        self._publisher = publisher or get_default_event_publisher()

    async def publish(self, *, name: str, payload: Mapping[str, Any] | None = None) -> Event:
        return await self._publisher.publish(name=name, payload=payload)

    async def publish_many(self, events: Sequence[EventRequest]) -> list[Event]:
        return await self._publisher.publish_many(events)
