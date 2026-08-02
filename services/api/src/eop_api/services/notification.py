from collections.abc import Sequence

from eop_api.notifications.base import NotificationProvider, NotificationRequest
from eop_api.notifications.memory_provider import InMemoryNotificationProvider
from eop_api.schemas.notification import Notification

_default_provider = InMemoryNotificationProvider()


def get_default_notification_provider() -> NotificationProvider:
    """The process-wide default `NotificationProvider`.

    Every `NotificationService()` created without an explicit provider
    shares this same in-memory store. Swapping in a future transport-backed
    provider means changing this factory, not any caller.
    """
    return _default_provider


class NotificationService:
    """Entry point for sending notifications. Owns no business logic.

    Delegates everything to a `NotificationProvider`; business modules
    should depend on this service, never on a concrete provider. Nothing in
    this PR calls it yet -- it is infrastructure for later adoption.
    """

    def __init__(self, provider: NotificationProvider | None = None) -> None:
        self._provider = provider or get_default_notification_provider()

    async def send(self, *, recipient: str, subject: str, body: str) -> Notification:
        return await self._provider.send(recipient=recipient, subject=subject, body=body)

    async def send_many(self, notifications: Sequence[NotificationRequest]) -> list[Notification]:
        return await self._provider.send_many(notifications)
