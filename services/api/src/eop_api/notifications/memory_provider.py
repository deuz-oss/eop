import threading
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from eop_api.notifications.base import NotificationProvider, NotificationRequest
from eop_api.schemas.notification import Notification


class InMemoryNotificationProvider(NotificationProvider):
    """Development/testing `NotificationProvider` that keeps sent notifications in a list.

    There is no delivery, retry, or background execution behind this -- it
    only records that a notification was sent, at the time it was sent.
    Real delivery is the responsibility of a future transport-backed
    provider (e.g. SMTP, a webhook provider).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._notifications: list[Notification] = []

    @property
    def notifications(self) -> list[Notification]:
        """Snapshot of every notification sent so far, in send order."""
        with self._lock:
            return list(self._notifications)

    async def send(self, *, recipient: str, subject: str, body: str) -> Notification:
        return self._store(recipient=recipient, subject=subject, body=body)

    async def send_many(self, notifications: Sequence[NotificationRequest]) -> list[Notification]:
        return [
            self._store(recipient=request.recipient, subject=request.subject, body=request.body)
            for request in notifications
        ]

    def _store(self, *, recipient: str, subject: str, body: str) -> Notification:
        notification = Notification(
            id=uuid.uuid4(),
            recipient=recipient,
            subject=subject,
            body=body,
            created_at=datetime.now(UTC),
        )
        with self._lock:
            self._notifications.append(notification)
        return notification
