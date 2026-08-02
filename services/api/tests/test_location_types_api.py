import asyncio
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.core.security import hash_password
from eop_api.db.base import Base
from eop_api.main import app
from eop_api.models.user import User
from eop_api.repositories.user import UserRepository


@pytest.fixture(autouse=True)
def _tables() -> Generator[None]:
    """Ensures all tables exist and are empty for each test.

    The API runs against the real app and its real (default) database engine,
    so state is reset via TRUNCATE rather than dropping the migration-managed
    tables.
    """

    async def _create() -> None:
        engine = create_async_engine(settings.database_url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    async def _truncate() -> None:
        engine = create_async_engine(settings.database_url)
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE location_types, users CASCADE"))
        await engine.dispose()

    asyncio.run(_create())
    yield
    asyncio.run(_truncate())


@pytest.fixture
def client() -> Generator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


async def _create_user(*, email: str, password: str) -> User:
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        user = await UserRepository(session).create(
            email=email,
            password_hash=hash_password(password),
            full_name="Test User",
            is_active=True,
        )
        await session.commit()
        session.expunge(user)
    await engine.dispose()
    return user


@pytest.fixture
def user() -> User:
    return asyncio.run(_create_user(email="member@example.com", password="member-pass"))


@pytest.fixture
def user_headers(client: TestClient, user: User) -> dict[str, str]:
    response = client.post(
        "/auth/login", json={"email": "member@example.com", "password": "member-pass"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_location_type_requires_authentication(client: TestClient):
    response = client.post("/location-types", json={"code": "warehouse", "name": "Warehouse"})

    assert response.status_code == 401


def test_list_location_types_requires_authentication(client: TestClient):
    response = client.get("/location-types")

    assert response.status_code == 401


def test_create_location_type(client: TestClient, user_headers: dict[str, str]):
    response = client.post(
        "/location-types", json={"code": "warehouse", "name": "Warehouse"}, headers=user_headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["code"] == "warehouse"
    assert body["name"] == "Warehouse"
    uuid.UUID(body["id"])


def test_create_location_type_rejects_blank_name(client: TestClient, user_headers: dict[str, str]):
    response = client.post(
        "/location-types", json={"code": "warehouse", "name": ""}, headers=user_headers
    )

    assert response.status_code == 422


def test_get_location_type(client: TestClient, user_headers: dict[str, str]):
    created = client.post(
        "/location-types", json={"code": "store", "name": "Store"}, headers=user_headers
    ).json()

    response = client.get(f"/location-types/{created['id']}", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["name"] == "Store"


def test_get_location_type_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.get(f"/location-types/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_list_location_types(client: TestClient, user_headers: dict[str, str]):
    client.post(
        "/location-types", json={"code": "warehouse", "name": "Warehouse"}, headers=user_headers
    )
    client.post("/location-types", json={"code": "store", "name": "Store"}, headers=user_headers)

    response = client.get("/location-types", headers=user_headers)

    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert {"Warehouse", "Store"}.issubset(names)


def test_list_location_types_paginated_default_pagination(
    client: TestClient, user_headers: dict[str, str]
):
    for i in range(3):
        client.post(
            "/location-types", json={"code": f"type-{i}", "name": f"Type {i}"}, headers=user_headers
        )

    response = client.get("/location-types/paginated", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 0
    assert body["limit"] == 50
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_list_location_types_paginated_search(client: TestClient, user_headers: dict[str, str]):
    client.post(
        "/location-types", json={"code": "warehouse", "name": "Warehouse"}, headers=user_headers
    )
    client.post("/location-types", json={"code": "store", "name": "Store"}, headers=user_headers)

    response = client.get("/location-types/paginated", headers=user_headers, params={"q": "ware"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Warehouse"


def test_update_location_type(client: TestClient, user_headers: dict[str, str]):
    created = client.post(
        "/location-types", json={"code": "before", "name": "Before"}, headers=user_headers
    ).json()

    response = client.patch(
        f"/location-types/{created['id']}", json={"name": "After"}, headers=user_headers
    )

    assert response.status_code == 200
    assert response.json()["name"] == "After"


def test_update_location_type_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.patch(
        f"/location-types/{uuid.uuid4()}", json={"name": "After"}, headers=user_headers
    )

    assert response.status_code == 404


def test_delete_location_type(client: TestClient, user_headers: dict[str, str]):
    created = client.post(
        "/location-types", json={"code": "to-delete", "name": "To Delete"}, headers=user_headers
    ).json()

    response = client.delete(f"/location-types/{created['id']}", headers=user_headers)

    assert response.status_code == 204
    assert client.get(f"/location-types/{created['id']}", headers=user_headers).status_code == 404


def test_delete_location_type_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.delete(f"/location-types/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404
