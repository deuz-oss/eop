from collections.abc import AsyncGenerator

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from eop_api.db.dependencies import get_db
from eop_api.main import app


class _FakeSession:
    async def execute(self, *_args, **_kwargs):
        return None


class _FailingSession:
    async def execute(self, *_args, **_kwargs):
        raise SQLAlchemyError("db unavailable")


async def _override_get_db_ok() -> AsyncGenerator:
    yield _FakeSession()


async def _override_get_db_fail() -> AsyncGenerator:
    yield _FailingSession()


def test_health_reports_connected_database():
    app.dependency_overrides[get_db] = _override_get_db_ok
    try:
        with TestClient(app) as client:
            response = client.get("/health")
    finally:
        app.dependency_overrides.pop(get_db, None)

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert "version" in body
    assert "environment" in body


def test_health_reports_disconnected_database():
    app.dependency_overrides[get_db] = _override_get_db_fail
    try:
        with TestClient(app) as client:
            response = client.get("/health")
    finally:
        app.dependency_overrides.pop(get_db, None)

    body = response.json()
    assert response.status_code == 503
    assert body["status"] == "error"
    assert body["database"] == "disconnected"
