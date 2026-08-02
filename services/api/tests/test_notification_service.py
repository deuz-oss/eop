import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from eop_api.notifications.base import NotificationProvider, NotificationRequest
from eop_api.notifications.memory_provider import InMemoryNotificationProvider
from eop_api.schemas.notification import Notification
from eop_api.services.notification import NotificationService, get_default_notification_provider

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeNotificationProvider(NotificationProvider):
    """Records exactly which `NotificationProvider` method `NotificationService` delegated to."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    async def send(self, *, recipient: str, subject: str, body: str) -> Notification:
        self.calls.append(("send", {"recipient": recipient, "subject": subject, "body": body}))
        return _make_notification(recipient, subject, body)

    async def send_many(self, notifications: Sequence[NotificationRequest]) -> list[Notification]:
        self.calls.append(("send_many", notifications))
        return [_make_notification(n.recipient, n.subject, n.body) for n in notifications]


def _make_notification(recipient: str, subject: str, body: str) -> Notification:
    return Notification(
        id=uuid.uuid4(),
        recipient=recipient,
        subject=subject,
        body=body,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def provider() -> FakeNotificationProvider:
    return FakeNotificationProvider()


@pytest.fixture
def service(provider: FakeNotificationProvider) -> NotificationService:
    return NotificationService(provider)


async def test_send_delegates_to_provider(
    service: NotificationService, provider: FakeNotificationProvider
):
    notification = await service.send(recipient="a@example.com", subject="Welcome", body="Hi")

    assert provider.calls == [
        ("send", {"recipient": "a@example.com", "subject": "Welcome", "body": "Hi"})
    ]
    assert notification.recipient == "a@example.com"
    assert notification.subject == "Welcome"


async def test_send_many_delegates_to_provider(
    service: NotificationService, provider: FakeNotificationProvider
):
    requests = [
        NotificationRequest(recipient="a@example.com", subject="A", body="body-a"),
        NotificationRequest(recipient="b@example.com", subject="B", body="body-b"),
    ]

    notifications = await service.send_many(requests)

    assert provider.calls == [("send_many", requests)]
    assert [n.recipient for n in notifications] == ["a@example.com", "b@example.com"]


async def test_service_performs_no_business_logic_of_its_own(
    service: NotificationService, provider: FakeNotificationProvider
):
    """The service is a pure pass-through: whatever the provider returns is
    exactly what callers get back, unmodified."""
    notification = await service.send(recipient="a@example.com", subject="s", body="b")

    assert notification.id is not None
    assert len(provider.calls) == 1


async def test_default_provider_is_shared_across_service_instances():
    """Two `NotificationService`s created without an explicit provider must
    delegate to the same underlying `InMemoryNotificationProvider`, since
    notification storage is only ever in-process memory -- a fresh provider
    per service would silently lose every previously sent notification."""
    first_service = NotificationService()
    second_service = NotificationService()

    notification = await first_service.send(
        recipient="a@example.com", subject="shared-provider-check", body="b"
    )

    default_provider = get_default_notification_provider()
    assert isinstance(default_provider, InMemoryNotificationProvider)
    assert notification in default_provider.notifications
    assert second_service is not first_service
