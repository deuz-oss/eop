import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


@dataclass(frozen=True)
class EventRequest:
    """A single event to publish, as input to `EventPublisher.publish_many`."""

    name: str
    payload: Mapping[str, Any] | None = None


class Event(BaseModel):
    """A published event.

    Deliberately minimal -- no routing, delivery, or subscriber metadata.
    This PR only establishes that an event was published, not that anything
    reacts to it.
    """

    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    name: str
    payload: Mapping[str, Any]
    occurred_at: datetime
