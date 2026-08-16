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
    """Ensures the `organizations`/`employees` tables exist and are empty for each test.

    The API runs against the real app and its real (default) database engine,
    so state is reset via TRUNCATE rather than dropping the migration-managed
    tables. Truncating `organizations` with CASCADE also clears `employees`,
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


def test_create_employee(client: TestClient, organization_id: str):
    response = client.post(
        "/employees",
        json={
            "organization_id": organization_id,
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.com",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["first_name"] == "Ada"
    assert body["last_name"] == "Lovelace"
    assert body["email"] == "ada@example.com"
    assert body["organization_id"] == organization_id
    uuid.UUID(body["id"])


def test_create_employee_rejects_blank_first_name(client: TestClient, organization_id: str):
    response = client.post(
        "/employees",
        json={
            "organization_id": organization_id,
            "first_name": "",
            "last_name": "Lovelace",
            "email": "ada@example.com",
        },
    )

    assert response.status_code == 422


def test_create_employee_rejects_missing_organization(client: TestClient):
    response = client.post(
        "/employees",
        json={
            "organization_id": str(uuid.uuid4()),
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.com",
        },
    )

    assert response.status_code == 404


def test_create_employee_rejects_duplicate_email(client: TestClient, organization_id: str):
    client.post(
        "/employees",
        json={
            "organization_id": organization_id,
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.com",
        },
    )

    response = client.post(
        "/employees",
        json={
            "organization_id": organization_id,
            "first_name": "Ada 2",
            "last_name": "Lovelace",
            "email": "ada@example.com",
        },
    )

    assert response.status_code == 409


def test_get_employee(client: TestClient, organization_id: str):
    created = client.post(
        "/employees",
        json={
            "organization_id": organization_id,
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.com",
        },
    ).json()

    response = client.get(f"/employees/{created['id']}")

    assert response.status_code == 200
    assert response.json()["first_name"] == "Ada"


def test_get_employee_not_found(client: TestClient):
    response = client.get(f"/employees/{uuid.uuid4()}")

    assert response.status_code == 404


def test_list_employees(client: TestClient, organization_id: str):
    client.post(
        "/employees",
        json={
            "organization_id": organization_id,
            "first_name": "Alpha",
            "last_name": "One",
            "email": "alpha@example.com",
        },
    )
    client.post(
        "/employees",
        json={
            "organization_id": organization_id,
            "first_name": "Beta",
            "last_name": "Two",
            "email": "beta@example.com",
        },
    )

    response = client.get("/employees")

    assert response.status_code == 200
    names = {employee["first_name"] for employee in response.json()}
    assert {"Alpha", "Beta"}.issubset(names)


def test_update_employee(client: TestClient, organization_id: str):
    created = client.post(
        "/employees",
        json={
            "organization_id": organization_id,
            "first_name": "Before",
            "last_name": "Name",
            "email": "before@example.com",
        },
    ).json()

    response = client.patch(f"/employees/{created['id']}", json={"first_name": "After"})

    assert response.status_code == 200
    assert response.json()["first_name"] == "After"


def test_update_employee_not_found(client: TestClient):
    response = client.patch(f"/employees/{uuid.uuid4()}", json={"first_name": "After"})

    assert response.status_code == 404


def test_update_employee_rejects_duplicate_email(client: TestClient, organization_id: str):
    client.post(
        "/employees",
        json={
            "organization_id": organization_id,
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.com",
        },
    )
    other = client.post(
        "/employees",
        json={
            "organization_id": organization_id,
            "first_name": "Zeus",
            "last_name": "Olympus",
            "email": "zeus@example.com",
        },
    ).json()

    response = client.patch(f"/employees/{other['id']}", json={"email": "ada@example.com"})

    assert response.status_code == 409


def test_delete_employee(client: TestClient, organization_id: str):
    created = client.post(
        "/employees",
        json={
            "organization_id": organization_id,
            "first_name": "To",
            "last_name": "Delete",
            "email": "delete@example.com",
        },
    ).json()

    response = client.delete(f"/employees/{created['id']}")

    assert response.status_code == 204
    assert client.get(f"/employees/{created['id']}").status_code == 404


def test_delete_employee_not_found(client: TestClient):
    response = client.delete(f"/employees/{uuid.uuid4()}")

    assert response.status_code == 404
