from collections.abc import AsyncGenerator

from fastapi.testclient import TestClient

from eop_api.core.request_context import (
    bind_request_id,
    bind_user_id,
    current_request_id,
    current_user_id,
    reset_request_id,
    reset_user_id,
)
from eop_api.db.dependencies import get_db
from eop_api.main import app


class _FakeSession:
    async def execute(self, *_args, **_kwargs):
        return None


async def _override_get_db_ok() -> AsyncGenerator:
    yield _FakeSession()


def test_current_request_id_defaults_to_none():
    assert current_request_id() is None


def test_current_user_id_defaults_to_none():
    assert current_user_id() is None


def test_bind_and_reset_request_id_round_trips():
    token = bind_request_id("req-1")
    try:
        assert current_request_id() == "req-1"
    finally:
        reset_request_id(token)

    assert current_request_id() is None


def test_bind_and_reset_user_id_round_trips():
    token = bind_user_id("user-1")
    try:
        assert current_user_id() == "user-1"
    finally:
        reset_user_id(token)

    assert current_user_id() is None


def test_nested_bind_restores_previous_value_on_reset():
    outer_token = bind_request_id("outer")
    try:
        inner_token = bind_request_id("inner")
        try:
            assert current_request_id() == "inner"
        finally:
            reset_request_id(inner_token)

        assert current_request_id() == "outer"
    finally:
        reset_request_id(outer_token)


def test_request_id_contextvar_is_isolated_between_requests():
    app.dependency_overrides[get_db] = _override_get_db_ok
    try:
        with TestClient(app) as client:
            first = client.get("/health", headers={"X-Request-ID": "first-request"})
            second = client.get("/health", headers={"X-Request-ID": "second-request"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert first.headers["X-Request-ID"] == "first-request"
    assert second.headers["X-Request-ID"] == "second-request"
    # The middleware resets the contextvar after each request, so it must not
    # leak into code running outside a request lifecycle.
    assert current_request_id() is None
