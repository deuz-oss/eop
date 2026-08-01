import asyncio
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.main import app


@pytest.fixture(autouse=True)
def _organizations_table() -> Generator[None]:
    """Ensures the `organizations` table exists and is empty for each test.

    The API runs against the real app and its real (default) database engine,
    so state is reset via TRUNCATE rather than dropping the migration-managed
    table.
    """

    async def _create() -> None:
        engine = create_async_engine(settings.database_url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    async def _truncate() -> None:
        engine = create_async_engine(settings.database_url)
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE organizations CASCADE"))
        await engine.dispose()

    asyncio.run(_create())
    yield
    asyncio.run(_truncate())


@pytest.fixture
def client() -> Generator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def test_create_organization(client: TestClient):
    response = client.post("/organizations", json={"name": "Acme Corp"})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Acme Corp"
    uuid.UUID(body["id"])


def test_create_organization_rejects_blank_name(client: TestClient):
    response = client.post("/organizations", json={"name": ""})

    assert response.status_code == 422


def test_get_organization(client: TestClient):
    created = client.post("/organizations", json={"name": "Globex"}).json()

    response = client.get(f"/organizations/{created['id']}")

    assert response.status_code == 200
    assert response.json()["name"] == "Globex"


def test_get_organization_not_found(client: TestClient):
    response = client.get(f"/organizations/{uuid.uuid4()}")

    assert response.status_code == 404


def test_list_organizations(client: TestClient):
    client.post("/organizations", json={"name": "Alpha"})
    client.post("/organizations", json={"name": "Beta"})

    response = client.get("/organizations")

    assert response.status_code == 200
    names = {org["name"] for org in response.json()}
    assert {"Alpha", "Beta"}.issubset(names)


def test_update_organization(client: TestClient):
    created = client.post("/organizations", json={"name": "Before"}).json()

    response = client.patch(f"/organizations/{created['id']}", json={"name": "After"})

    assert response.status_code == 200
    assert response.json()["name"] == "After"


def test_update_organization_not_found(client: TestClient):
    response = client.patch(f"/organizations/{uuid.uuid4()}", json={"name": "After"})

    assert response.status_code == 404


def test_delete_organization(client: TestClient):
    created = client.post("/organizations", json={"name": "To Delete"}).json()

    response = client.delete(f"/organizations/{created['id']}")

    assert response.status_code == 204
    assert client.get(f"/organizations/{created['id']}").status_code == 404


def test_delete_organization_not_found(client: TestClient):
    response = client.delete(f"/organizations/{uuid.uuid4()}")

    assert response.status_code == 404
