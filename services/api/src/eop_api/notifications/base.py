import abc
from collections.abc import Sequence
from dataclasses import dataclass

from eop_api.schemas.notification import Notification


@dataclass(frozen=True)
class NotificationRequest:
    """A single notification to send, as input to `NotificationProvider.send_many`."""

    recipient: str
    subject: str
    body: str


class NotificationProvider(abc.ABC):
    """Reusable abstraction over a notification transport.

    Business modules must never talk to a concrete transport (e.g. an email
    provider, a webhook provider) directly -- everything goes through this
    interface via `NotificationService`. Generic enough that a future
    transport-backed provider can replace `InMemoryNotificationProvider`
    without callers changing.
    """

    @abc.abstractmethod
    async def send(self, *, recipient: str, subject: str, body: str) -> Notification:
        """Send a single notification to `recipient`."""
        ...

    @abc.abstractmethod
    async def send_many(self, notifications: Sequence[NotificationRequest]) -> list[Notification]:
        """Send each notification in `notifications`, in order."""
        ...
