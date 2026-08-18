import asyncio
from collections.abc import Generator

import pytest
from conftest import clean_database
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.core.login_throttle import (
    ACCOUNT_FAILURE_THRESHOLD,
    IP_FAILURE_THRESHOLD,
    login_throttle,
)
from eop_api.core.security import create_access_token, hash_password
from eop_api.main import app
from eop_api.models.user import User
from eop_api.repositories.user import UserRepository


@pytest.fixture(autouse=True)
def _reset_login_throttle() -> Generator[None]:
    """The login throttle is a process-local module-level singleton, so its state
    would otherwise leak between tests (and between this file and any other test
    that exercises `/auth/login`)."""
    login_throttle.reset_all()
    yield
    login_throttle.reset_all()


_tables = pytest.fixture(autouse=True)(clean_database)


@pytest.fixture
def client() -> Generator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def _client_from(ip: str) -> TestClient:
    """A `TestClient` whose simulated ASGI peer address is `ip`, for tests that
    need requests to appear to originate from a specific (possibly distinct)
    client IP."""
    return TestClient(app, client=(ip, 50000))


async def _create_user(*, email: str, password: str, is_active: bool = True) -> User:
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        user = await UserRepository(session).create(
            email=email,
            password_hash=hash_password(password),
            full_name="Ada Lovelace",
            is_active=is_active,
        )
        await session.commit()
        session.expunge(user)
    await engine.dispose()
    return user


@pytest.fixture
def active_user() -> User:
    return asyncio.run(_create_user(email="ada@example.com", password="correct-horse"))


@pytest.fixture
def inactive_user() -> User:
    return asyncio.run(
        _create_user(email="inactive@example.com", password="correct-horse", is_active=False)
    )


def test_login_succeeds_with_correct_credentials(client: TestClient, active_user: User):
    response = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "correct-horse"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]


def test_login_rejects_wrong_password(client: TestClient, active_user: User):
    response = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "wrong-password"}
    )

    assert response.status_code == 401


def test_login_rejects_unknown_email(client: TestClient):
    response = client.post(
        "/auth/login", json={"email": "unknown@example.com", "password": "correct-horse"}
    )

    assert response.status_code == 401


def test_login_rejects_inactive_user(client: TestClient, inactive_user: User):
    response = client.post(
        "/auth/login", json={"email": "inactive@example.com", "password": "correct-horse"}
    )

    assert response.status_code == 401


def test_me_returns_current_user(client: TestClient, active_user: User):
    login_response = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "correct-horse"}
    )
    token = login_response.json()["access_token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "ada@example.com"
    assert body["id"] == str(active_user.id)


def test_me_rejects_missing_token(client: TestClient):
    response = client.get("/auth/me")

    assert response.status_code in (401, 403)


def test_me_rejects_invalid_token(client: TestClient):
    response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-valid-token"})

    assert response.status_code == 401


def test_me_rejects_token_for_inactive_user(client: TestClient, inactive_user: User):
    token = create_access_token(subject=str(inactive_user.id))

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_login_below_threshold_stays_generic_401(client: TestClient, active_user: User):
    for _ in range(ACCOUNT_FAILURE_THRESHOLD - 1):
        response = client.post(
            "/auth/login", json={"email": "ada@example.com", "password": "wrong-password"}
        )
        assert response.status_code == 401
        assert "Retry-After" not in response.headers


def test_login_throttles_account_after_threshold_with_retry_after(
    client: TestClient, active_user: User
):
    for _ in range(ACCOUNT_FAILURE_THRESHOLD):
        response = client.post(
            "/auth/login", json={"email": "ada@example.com", "password": "wrong-password"}
        )
        assert response.status_code == 401

    throttled = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "wrong-password"}
    )

    assert throttled.status_code == 429
    assert throttled.headers["Retry-After"] == "1"


def test_wrong_password_and_unknown_email_stay_indistinguishable(
    client: TestClient, active_user: User
):
    wrong_password = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "wrong-password"}
    )
    unknown_email = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "whatever"}
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json()["detail"] == unknown_email.json()["detail"]


def test_successful_login_resets_account_throttle(client: TestClient, active_user: User):
    for _ in range(ACCOUNT_FAILURE_THRESHOLD):
        client.post("/auth/login", json={"email": "ada@example.com", "password": "wrong-password"})

    success = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "correct-horse"}
    )
    assert success.status_code == 200

    next_failure = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "wrong-password"}
    )

    assert next_failure.status_code == 401


def test_ip_throttle_protects_against_one_ip_attacking_many_accounts(client: TestClient):
    for i in range(IP_FAILURE_THRESHOLD):
        response = client.post(
            "/auth/login",
            json={"email": f"attacker-target-{i}@example.com", "password": "guess"},
            headers={"X-Forwarded-For": f"198.51.100.{i}"},
        )
        assert response.status_code == 401

    throttled = client.post(
        "/auth/login",
        json={"email": "attacker-target-new@example.com", "password": "guess"},
        headers={"X-Forwarded-For": "203.0.113.250"},
    )

    assert throttled.status_code == 429
    assert "Retry-After" in throttled.headers


def test_account_throttle_protects_against_many_ips_attacking_one_account(active_user: User):
    for i in range(ACCOUNT_FAILURE_THRESHOLD):
        with _client_from(f"192.0.2.{i}") as ip_client:
            response = ip_client.post(
                "/auth/login", json={"email": "ada@example.com", "password": "wrong-password"}
            )
            assert response.status_code == 401

    with _client_from("192.0.2.250") as ip_client:
        throttled = ip_client.post(
            "/auth/login", json={"email": "ada@example.com", "password": "wrong-password"}
        )

    assert throttled.status_code == 429


def test_login_ipv6_client_is_supported(active_user: User):
    with _client_from("2001:db8::1") as ip_client:
        response = ip_client.post(
            "/auth/login", json={"email": "ada@example.com", "password": "correct-horse"}
        )

    assert response.status_code == 200


def test_login_throttle_fails_open_when_ip_check_errors(
    monkeypatch, client: TestClient, active_user: User
):
    def _boom(*_args, **_kwargs):
        raise RuntimeError("throttle store unavailable")

    monkeypatch.setattr(login_throttle, "is_ip_throttled", _boom)

    response = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "correct-horse"}
    )

    assert response.status_code == 200


def test_login_throttle_fails_open_when_account_check_errors(
    monkeypatch, client: TestClient, active_user: User
):
    def _boom(*_args, **_kwargs):
        raise RuntimeError("throttle store unavailable")

    monkeypatch.setattr(login_throttle, "is_account_throttled", _boom)

    response = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "correct-horse"}
    )

    assert response.status_code == 200


def test_login_throttle_fails_open_when_recording_errors(
    monkeypatch, client: TestClient, active_user: User
):
    def _boom(**_kwargs):
        raise RuntimeError("throttle store unavailable")

    monkeypatch.setattr(login_throttle, "record_failure", _boom)

    response = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "wrong-password"}
    )

    assert response.status_code == 401


def test_login_throttle_failure_is_logged_without_credentials(
    monkeypatch, client: TestClient, active_user: User
):
    captured: list[dict[str, object]] = []

    def _boom(*_args, **_kwargs):
        raise RuntimeError("throttle store unavailable")

    def _capture_warning(event, **kwargs):
        captured.append({"event": event, **kwargs})

    monkeypatch.setattr(login_throttle, "is_ip_throttled", _boom)
    monkeypatch.setattr("eop_api.api.auth.logger.warning", _capture_warning)

    client.post("/auth/login", json={"email": "ada@example.com", "password": "correct-horse"})

    assert len(captured) == 1
    logged_keys = set(captured[0].keys())
    assert "password" not in logged_keys
    assert not any("password" in str(value).lower() for value in captured[0].values())


def test_only_login_endpoint_is_throttled(client: TestClient):
    for _ in range(ACCOUNT_FAILURE_THRESHOLD + 5):
        response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-valid-token"})
        assert response.status_code == 401


def test_account_throttle_escalates_on_continued_wrong_password(
    client: TestClient, active_user: User
):
    for _ in range(ACCOUNT_FAILURE_THRESHOLD):
        client.post("/auth/login", json={"email": "ada@example.com", "password": "wrong-password"})

    expected_retry_after = ["1", "2", "4", "8", "16", "16"]
    for expected in expected_retry_after:
        response = client.post(
            "/auth/login", json={"email": "ada@example.com", "password": "wrong-password"}
        )
        assert response.status_code == 429
        assert response.headers["Retry-After"] == expected


def test_ip_throttle_remains_authoritative_over_correct_account_password(
    client: TestClient, active_user: User
):
    # Trip the IP threshold using unrelated accounts only -- `active_user`'s own
    # account is never touched, so it is nowhere near its own threshold.
    for i in range(IP_FAILURE_THRESHOLD):
        response = client.post(
            "/auth/login", json={"email": f"ip-flood-{i}@example.com", "password": "guess"}
        )
        assert response.status_code == 401

    blocked = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "correct-horse"}
    )

    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_successful_login_clears_account_state_but_not_ip_state(
    client: TestClient, active_user: User
):
    for _ in range(ACCOUNT_FAILURE_THRESHOLD):
        client.post("/auth/login", json={"email": "ada@example.com", "password": "wrong-password"})

    success = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "correct-horse"}
    )
    assert success.status_code == 200

    # The account counter was cleared by the success above, but the IP counter
    # (already at ACCOUNT_FAILURE_THRESHOLD from the failures preceding it) was
    # not -- driving it the rest of the way to IP_FAILURE_THRESHOLD using fresh,
    # never-throttled accounts should still trip the IP-scoped throttle.
    remaining = IP_FAILURE_THRESHOLD - ACCOUNT_FAILURE_THRESHOLD
    for i in range(remaining):
        response = client.post(
            "/auth/login", json={"email": f"other-target-{i}@example.com", "password": "guess"}
        )
        assert response.status_code == 401

    throttled = client.post(
        "/auth/login", json={"email": "yet-another-target@example.com", "password": "guess"}
    )

    assert throttled.status_code == 429
