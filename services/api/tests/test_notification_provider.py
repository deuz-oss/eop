from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from eop_api.notifications.base import NotificationRequest
from eop_api.notifications.memory_provider import InMemoryNotificationProvider

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def provider() -> InMemoryNotificationProvider:
    return InMemoryNotificationProvider()


async def test_send_stores_notification_with_recipient_subject_and_body(
    provider: InMemoryNotificationProvider,
):
    notification = await provider.send(
        recipient="a@example.com", subject="Welcome", body="Hello there"
    )

    assert notification.recipient == "a@example.com"
    assert notification.subject == "Welcome"
    assert notification.body == "Hello there"
    assert notification.id is not None


async def test_send_sets_created_at_close_to_now(provider: InMemoryNotificationProvider):
    before = datetime.now(UTC)

    notification = await provider.send(recipient="a@example.com", subject="s", body="b")

    after = datetime.now(UTC)
    assert before <= notification.created_at <= after


async def test_send_many_stores_all_notifications_in_order(
    provider: InMemoryNotificationProvider,
):
    requests = [
        NotificationRequest(recipient="a@example.com", subject="A", body="body-a"),
        NotificationRequest(recipient="b@example.com", subject="B", body="body-b"),
    ]

    notifications = await provider.send_many(requests)

    assert [n.recipient for n in notifications] == ["a@example.com", "b@example.com"]
    assert notifications == provider.notifications


async def test_each_send_produces_a_unique_id(provider: InMemoryNotificationProvider):
    first = await provider.send(recipient="a@example.com", subject="s", body="b")
    second = await provider.send(recipient="a@example.com", subject="s", body="b")

    assert first.id != second.id


async def test_notifications_are_stored_in_send_order(provider: InMemoryNotificationProvider):
    await provider.send(recipient="a@example.com", subject="first", body="b")
    await provider.send_many(
        [NotificationRequest(recipient="b@example.com", subject="second", body="b")]
    )
    await provider.send(recipient="c@example.com", subject="third", body="b")

    subjects = [n.subject for n in provider.notifications]
    assert subjects == ["first", "second", "third"]


async def test_notifications_property_returns_a_snapshot(
    provider: InMemoryNotificationProvider,
):
    await provider.send(recipient="a@example.com", subject="first", body="b")

    snapshot = provider.notifications
    snapshot.clear()

    assert [n.subject for n in provider.notifications] == ["first"]


async def test_notification_is_immutable(provider: InMemoryNotificationProvider):
    notification = await provider.send(recipient="a@example.com", subject="s", body="b")

    with pytest.raises(ValidationError):
        notification.subject = "changed"
