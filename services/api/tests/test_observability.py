import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from eop_api.db.dependencies import get_db
from eop_api.main import app
from eop_api.middleware.request_id import REQUEST_ID_HEADER


class _FakeSession:
    async def execute(self, *_args, **_kwargs):
        return None


async def _override_get_db_ok() -> AsyncGenerator:
    yield _FakeSession()


boom_router = APIRouter()


@boom_router.get("/__boom")
async def boom():
    raise RuntimeError("kaboom")


app.include_router(boom_router)


def test_health_response_includes_request_id_header():
    app.dependency_overrides[get_db] = _override_get_db_ok
    try:
        with TestClient(app) as client:
            response = client.get("/health")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert REQUEST_ID_HEADER in response.headers
    uuid.UUID(response.headers[REQUEST_ID_HEADER])


def test_incoming_request_id_is_reused():
    app.dependency_overrides[get_db] = _override_get_db_ok
    incoming_id = "test-request-id-123"
    try:
        with TestClient(app) as client:
            response = client.get("/health", headers={REQUEST_ID_HEADER: incoming_id})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.headers[REQUEST_ID_HEADER] == incoming_id


def test_unhandled_exception_returns_safe_json_with_request_id():
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/__boom")

    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == "Internal Server Error"
    assert body["request_id"]
    assert response.headers[REQUEST_ID_HEADER] == body["request_id"]


def test_unhandled_exception_does_not_leak_traceback():
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/__boom")

    assert "Traceback" not in response.text
    assert "kaboom" not in response.text


def test_disconnected_database_response_still_has_request_id():
    class _FailingSession:
        async def execute(self, *_args, **_kwargs):
            raise SQLAlchemyError("db unavailable")

    async def _override_get_db_fail() -> AsyncGenerator:
        yield _FailingSession()

    app.dependency_overrides[get_db] = _override_get_db_fail
    try:
        with TestClient(app) as client:
            response = client.get("/health")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 503
    assert REQUEST_ID_HEADER in response.headers
