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
    """Ensures the `organizations`/`projects` tables exist and are empty for each test.

    The API runs against the real app and its real (default) database engine,
    so state is reset via TRUNCATE rather than dropping the migration-managed
    tables. Truncating `organizations` with CASCADE also clears `projects`,
    since it references `organizations` by foreign key.
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


@pytest.fixture
def organization_id(client: TestClient, user_headers: dict[str, str]) -> str:
    response = client.post("/organizations", json={"name": "Acme Corp"}, headers=user_headers)
    return response.json()["id"]


def test_create_project(client: TestClient, organization_id: str):
    response = client.post(
        "/projects",
        json={"organization_id": organization_id, "name": "Apollo", "code": "APO"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Apollo"
    assert body["code"] == "APO"
    assert body["organization_id"] == organization_id
    assert body["status"] == "active"
    uuid.UUID(body["id"])


def test_create_project_rejects_blank_name(client: TestClient, organization_id: str):
    response = client.post(
        "/projects", json={"organization_id": organization_id, "name": "", "code": "APO"}
    )

    assert response.status_code == 422


def test_create_project_rejects_missing_organization(client: TestClient):
    response = client.post(
        "/projects",
        json={"organization_id": str(uuid.uuid4()), "name": "Apollo", "code": "APO"},
    )

    assert response.status_code == 404


def test_create_project_rejects_duplicate_code_in_same_organization(
    client: TestClient, organization_id: str
):
    client.post(
        "/projects",
        json={"organization_id": organization_id, "name": "Apollo", "code": "APO"},
    )

    response = client.post(
        "/projects",
        json={"organization_id": organization_id, "name": "Apollo 2", "code": "APO"},
    )

    assert response.status_code == 409


def test_get_project(client: TestClient, organization_id: str):
    created = client.post(
        "/projects",
        json={"organization_id": organization_id, "name": "Apollo", "code": "APO"},
    ).json()

    response = client.get(f"/projects/{created['id']}")

    assert response.status_code == 200
    assert response.json()["name"] == "Apollo"


def test_get_project_not_found(client: TestClient):
    response = client.get(f"/projects/{uuid.uuid4()}")

    assert response.status_code == 404


def test_list_projects(client: TestClient, organization_id: str):
    client.post(
        "/projects", json={"organization_id": organization_id, "name": "Alpha", "code": "ALP"}
    )
    client.post(
        "/projects", json={"organization_id": organization_id, "name": "Beta", "code": "BET"}
    )

    response = client.get("/projects")

    assert response.status_code == 200
    names = {project["name"] for project in response.json()}
    assert {"Alpha", "Beta"}.issubset(names)


def test_update_project(client: TestClient, organization_id: str):
    created = client.post(
        "/projects",
        json={"organization_id": organization_id, "name": "Before", "code": "BEF"},
    ).json()

    response = client.patch(f"/projects/{created['id']}", json={"name": "After"})

    assert response.status_code == 200
    assert response.json()["name"] == "After"


def test_update_project_not_found(client: TestClient):
    response = client.patch(f"/projects/{uuid.uuid4()}", json={"name": "After"})

    assert response.status_code == 404


def test_update_project_rejects_duplicate_code(client: TestClient, organization_id: str):
    client.post(
        "/projects", json={"organization_id": organization_id, "name": "Apollo", "code": "APO"}
    )
    other = client.post(
        "/projects", json={"organization_id": organization_id, "name": "Zeus", "code": "ZEU"}
    ).json()

    response = client.patch(f"/projects/{other['id']}", json={"code": "APO"})

    assert response.status_code == 409


def test_delete_project(client: TestClient, organization_id: str):
    created = client.post(
        "/projects",
        json={"organization_id": organization_id, "name": "To Delete", "code": "DEL"},
    ).json()

    response = client.delete(f"/projects/{created['id']}")

    assert response.status_code == 204
    assert client.get(f"/projects/{created['id']}").status_code == 404


def test_delete_project_not_found(client: TestClient):
    response = client.delete(f"/projects/{uuid.uuid4()}")

    assert response.status_code == 404
