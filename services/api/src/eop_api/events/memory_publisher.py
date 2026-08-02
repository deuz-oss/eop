import threading
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from eop_api.events.base import EventPublisher
from eop_api.schemas.event import Event, EventRequest


class InMemoryEventPublisher(EventPublisher):
    """Development/testing `EventPublisher` that keeps published events in a list.

    There is no broker, queue, or subscriber behind this -- it only records
    that an event was published, at the time it was published. Real
    dispatching is the responsibility of a future broker-backed publisher.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: list[Event] = []

    @property
    def events(self) -> list[Event]:
        """Snapshot of every event published so far, in publish order."""
        with self._lock:
            return list(self._events)

    async def publish(self, *, name: str, payload: Mapping[str, Any] | None = None) -> Event:
        return self._store(name=name, payload=payload)

    async def publish_many(self, events: Sequence[EventRequest]) -> list[Event]:
        return [self._store(name=request.name, payload=request.payload) for request in events]

    def _store(self, *, name: str, payload: Mapping[str, Any] | None) -> Event:
        # Copy into a plain dict we own -- the caller's mapping is never
        # mutated, and mutations to the caller's mapping after this call
        # never leak into the stored event.
        stored_payload = dict(payload) if payload is not None else {}
        event = Event(
            id=uuid.uuid4(),
            name=name,
            payload=stored_payload,
            occurred_at=datetime.now(UTC),
        )
        with self._lock:
            self._events.append(event)
        return event
