from collections.abc import AsyncGenerator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from eop_api.db.dependencies import get_db
from eop_api.main import app

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


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


async def _check_storage_ok() -> bool:
    return True


async def _check_storage_fail() -> bool:
    return False


def _get(client_monkeypatch, db_override, storage_ok: bool):
    client_monkeypatch.setattr(
        "eop_api.api.health._check_storage",
        _check_storage_ok if storage_ok else _check_storage_fail,
    )
    app.dependency_overrides[get_db] = db_override
    try:
        with TestClient(app) as client:
            return client.get("/health")
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_health_reports_connected_database_and_storage(monkeypatch):
    response = _get(monkeypatch, _override_get_db_ok, storage_ok=True)

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert body["storage"] == "connected"
    assert "version" in body
    assert "environment" in body


def test_health_reports_disconnected_storage(monkeypatch):
    response = _get(monkeypatch, _override_get_db_ok, storage_ok=False)

    body = response.json()
    assert response.status_code == 503
    assert body["status"] == "error"
    assert body["database"] == "connected"
    assert body["storage"] == "disconnected"


def test_health_reports_disconnected_database(monkeypatch):
    response = _get(monkeypatch, _override_get_db_fail, storage_ok=True)

    body = response.json()
    assert response.status_code == 503
    assert body["status"] == "error"
    assert body["database"] == "disconnected"
    assert body["storage"] == "connected"


def test_health_reports_disconnected_database_and_storage(monkeypatch):
    response = _get(monkeypatch, _override_get_db_fail, storage_ok=False)

    body = response.json()
    assert response.status_code == 503
    assert body["status"] == "error"
    assert body["database"] == "disconnected"
    assert body["storage"] == "disconnected"


class _RaisingMinioClient:
    def bucket_exists(self, _bucket):
        raise RuntimeError("connection refused to internal-minio-host:9000 -- sensitive detail")


class _RaisingStorageProvider:
    def __init__(self, **_kwargs):
        self._client = _RaisingMinioClient()


def test_storage_failure_does_not_expose_raw_exception_details(monkeypatch):
    monkeypatch.setattr("eop_api.api.health.MinIOStorageProvider", _RaisingStorageProvider)
    app.dependency_overrides[get_db] = _override_get_db_ok
    try:
        with TestClient(app) as client:
            response = client.get("/health")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 503
    assert response.json()["storage"] == "disconnected"
    assert "internal-minio-host" not in response.text
    assert "sensitive detail" not in response.text


async def test_check_storage_swallows_connectivity_exception(monkeypatch):
    from eop_api.api.health import _check_storage

    monkeypatch.setattr("eop_api.api.health.MinIOStorageProvider", _RaisingStorageProvider)

    assert await _check_storage() is False
