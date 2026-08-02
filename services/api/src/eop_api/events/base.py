import abc
from collections.abc import Mapping, Sequence
from typing import Any

from eop_api.schemas.event import Event, EventRequest


class EventPublisher(abc.ABC):
    """Reusable abstraction over an event transport.

    Business modules must never talk to a concrete transport (e.g. a broker,
    a queue) directly -- everything goes through this interface via
    `EventService`. Generic enough that a future broker-backed publisher can
    replace `InMemoryEventPublisher` without callers changing.
    """

    @abc.abstractmethod
    async def publish(self, *, name: str, payload: Mapping[str, Any] | None = None) -> Event:
        """Publish a single event named `name`."""
        ...

    @abc.abstractmethod
    async def publish_many(self, events: Sequence[EventRequest]) -> list[Event]:
        """Publish each event in `events`, in order."""
        ...
