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
def _organizations_table() -> Generator[None]:
    """Ensures the `organizations`/`users` tables exist and are empty for each test.

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
            await conn.execute(text("TRUNCATE TABLE organizations, users CASCADE"))
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


def test_create_organization(client: TestClient, user_headers: dict[str, str]):
    response = client.post("/organizations", json={"name": "Acme Corp"}, headers=user_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Acme Corp"
    uuid.UUID(body["id"])


def test_create_organization_rejects_blank_name(client: TestClient, user_headers: dict[str, str]):
    response = client.post("/organizations", json={"name": ""}, headers=user_headers)

    assert response.status_code == 422


def test_get_organization(client: TestClient, user_headers: dict[str, str]):
    created = client.post("/organizations", json={"name": "Globex"}, headers=user_headers).json()

    response = client.get(f"/organizations/{created['id']}", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["name"] == "Globex"


def test_get_organization_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.get(f"/organizations/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_list_organizations(client: TestClient, user_headers: dict[str, str]):
    client.post("/organizations", json={"name": "Alpha"}, headers=user_headers)
    client.post("/organizations", json={"name": "Beta"}, headers=user_headers)

    response = client.get("/organizations", headers=user_headers)

    assert response.status_code == 200
    names = {org["name"] for org in response.json()}
    assert {"Alpha", "Beta"}.issubset(names)


def test_list_organizations_paginated_default_pagination(
    client: TestClient, user_headers: dict[str, str]
):
    for i in range(3):
        client.post("/organizations", json={"name": f"Org {i}"}, headers=user_headers)

    response = client.get("/organizations/paginated", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 0
    assert body["limit"] == 50
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_list_organizations_paginated_custom_offset(
    client: TestClient, user_headers: dict[str, str]
):
    for i in range(5):
        client.post("/organizations", json={"name": f"Org {i}"}, headers=user_headers)

    response = client.get("/organizations/paginated", params={"offset": 2}, headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 2
    assert body["total"] == 5
    assert len(body["items"]) == 3


def test_list_organizations_paginated_custom_limit(
    client: TestClient, user_headers: dict[str, str]
):
    for i in range(5):
        client.post("/organizations", json={"name": f"Org {i}"}, headers=user_headers)

    response = client.get("/organizations/paginated", params={"limit": 2}, headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 2
    assert body["total"] == 5
    assert len(body["items"]) == 2


def test_list_organizations_paginated_limit_above_maximum_is_clamped(
    client: TestClient, user_headers: dict[str, str]
):
    client.post("/organizations", json={"name": "Org"}, headers=user_headers)

    response = client.get("/organizations/paginated", params={"limit": 500}, headers=user_headers)

    assert response.status_code == 200
    assert response.json()["limit"] == 100


def test_list_organizations_paginated_negative_offset_is_rejected(
    client: TestClient, user_headers: dict[str, str]
):
    response = client.get("/organizations/paginated", params={"offset": -1}, headers=user_headers)

    assert response.status_code == 422


def test_list_organizations_paginated_negative_limit_is_rejected(
    client: TestClient, user_headers: dict[str, str]
):
    response = client.get("/organizations/paginated", params={"limit": -1}, headers=user_headers)

    assert response.status_code == 422


def test_list_organizations_paginated_search(client: TestClient, user_headers: dict[str, str]):
    client.post("/organizations", json={"name": "Open Robotics"}, headers=user_headers)
    client.post("/organizations", json={"name": "Closed Systems"}, headers=user_headers)

    response = client.get("/organizations/paginated", params={"q": "open"}, headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["name"] for item in body["items"]] == ["Open Robotics"]


def test_list_organizations_paginated_search_is_case_insensitive(
    client: TestClient, user_headers: dict[str, str]
):
    client.post("/organizations", json={"name": "Open Robotics"}, headers=user_headers)

    response = client.get("/organizations/paginated", params={"q": "OPEN"}, headers=user_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_list_organizations_paginated_search_and_pagination_together(
    client: TestClient, user_headers: dict[str, str]
):
    for i in range(5):
        client.post("/organizations", json={"name": f"Open Org {i}"}, headers=user_headers)
    client.post("/organizations", json={"name": "Closed Org"}, headers=user_headers)

    response = client.get(
        "/organizations/paginated",
        params={"q": "open", "offset": 1, "limit": 2},
        headers=user_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert body["offset"] == 1
    assert body["limit"] == 2
    assert len(body["items"]) == 2


def test_list_organizations_paginated_empty_query_returns_all(
    client: TestClient, user_headers: dict[str, str]
):
    client.post("/organizations", json={"name": "Alpha"}, headers=user_headers)
    client.post("/organizations", json={"name": "Beta"}, headers=user_headers)

    response = client.get("/organizations/paginated", params={"q": ""}, headers=user_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_list_organizations_paginated_no_query_returns_all(
    client: TestClient, user_headers: dict[str, str]
):
    client.post("/organizations", json={"name": "Alpha"}, headers=user_headers)
    client.post("/organizations", json={"name": "Beta"}, headers=user_headers)

    response = client.get("/organizations/paginated", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_update_organization(client: TestClient, user_headers: dict[str, str]):
    created = client.post("/organizations", json={"name": "Before"}, headers=user_headers).json()

    response = client.patch(
        f"/organizations/{created['id']}", json={"name": "After"}, headers=user_headers
    )

    assert response.status_code == 200
    assert response.json()["name"] == "After"


def test_update_organization_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.patch(
        f"/organizations/{uuid.uuid4()}", json={"name": "After"}, headers=user_headers
    )

    assert response.status_code == 404


def test_delete_organization(client: TestClient, user_headers: dict[str, str]):
    created = client.post("/organizations", json={"name": "To Delete"}, headers=user_headers).json()

    response = client.delete(f"/organizations/{created['id']}", headers=user_headers)

    assert response.status_code == 204
    assert client.get(f"/organizations/{created['id']}", headers=user_headers).status_code == 404


def test_delete_organization_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.delete(f"/organizations/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_create_organization_requires_authentication(client: TestClient):
    response = client.post("/organizations", json={"name": "Acme Corp"})

    assert response.status_code == 401


def test_list_organizations_requires_authentication(client: TestClient):
    response = client.get("/organizations")

    assert response.status_code == 401


def test_list_organizations_paginated_requires_authentication(client: TestClient):
    response = client.get("/organizations/paginated")

    assert response.status_code == 401


def test_get_organization_requires_authentication(client: TestClient):
    response = client.get(f"/organizations/{uuid.uuid4()}")

    assert response.status_code == 401


def test_update_organization_requires_authentication(client: TestClient):
    response = client.patch(f"/organizations/{uuid.uuid4()}", json={"name": "After"})

    assert response.status_code == 401


def test_delete_organization_requires_authentication(client: TestClient):
    response = client.delete(f"/organizations/{uuid.uuid4()}")

    assert response.status_code == 401
