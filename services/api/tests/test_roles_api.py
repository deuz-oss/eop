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
from eop_api.repositories.role import RoleRepository
from eop_api.repositories.user import UserRepository


@pytest.fixture(autouse=True)
def _tables() -> Generator[None]:
    """Ensures the `users`/`roles`/`user_roles` tables exist and are empty for
    each test.

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
            await conn.execute(text("TRUNCATE TABLE users, roles CASCADE"))
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
def admin_user() -> User:
    return asyncio.run(_create_user(email="admin@example.com", password="admin-pass"))


@pytest.fixture
def member_user() -> User:
    return asyncio.run(_create_user(email="member@example.com", password="member-pass"))


@pytest.fixture
def member_headers(client: TestClient, member_user: User) -> dict[str, str]:
    response = client.post(
        "/auth/login", json={"email": "member@example.com", "password": "member-pass"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _seed_admin(user_id: uuid.UUID) -> None:
    """Grants the `admin` role directly at the DB layer.

    The API has no bootstrap endpoint: creating or assigning roles through
    `/roles` itself requires the `admin` role, so the very first admin must be
    seeded outside the API.
    """
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        repo = RoleRepository(session)
        role = await repo.get_by_name("admin")
        if role is None:
            role = await repo.create(name="admin")
        await repo.assign_user(role.id, user_id)
        await session.commit()
    await engine.dispose()


@pytest.fixture
def admin_headers(client: TestClient, admin_user: User) -> dict[str, str]:
    asyncio.run(_seed_admin(admin_user.id))

    response = client.post(
        "/auth/login", json={"email": "admin@example.com", "password": "admin-pass"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_role(client: TestClient, admin_headers: dict[str, str]):
    response = client.post(
        "/roles", json={"name": "billing", "description": "Billing access"}, headers=admin_headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "billing"
    assert body["description"] == "Billing access"
    uuid.UUID(body["id"])


def test_create_role_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.post("/roles", json={"name": "billing"}, headers=member_headers)

    assert response.status_code == 403


def test_create_role_rejects_anonymous(client: TestClient):
    response = client.post("/roles", json={"name": "billing"})

    assert response.status_code in (401, 403)


def test_create_role_rejects_duplicate_name(client: TestClient, admin_headers: dict[str, str]):
    client.post("/roles", json={"name": "billing"}, headers=admin_headers)

    response = client.post("/roles", json={"name": "billing"}, headers=admin_headers)

    assert response.status_code == 409


def test_list_roles_allows_authenticated(client: TestClient, member_headers: dict[str, str]):
    response = client.get("/roles", headers=member_headers)

    assert response.status_code == 200


def test_list_roles_rejects_anonymous(client: TestClient):
    response = client.get("/roles")

    assert response.status_code in (401, 403)


def test_get_role(
    client: TestClient, admin_headers: dict[str, str], member_headers: dict[str, str]
):
    created = client.post("/roles", json={"name": "billing"}, headers=admin_headers).json()

    response = client.get(f"/roles/{created['id']}", headers=member_headers)

    assert response.status_code == 200
    assert response.json()["name"] == "billing"


def test_get_role_not_found(client: TestClient, member_headers: dict[str, str]):
    response = client.get(f"/roles/{uuid.uuid4()}", headers=member_headers)

    assert response.status_code == 404


def test_update_role(client: TestClient, admin_headers: dict[str, str]):
    created = client.post("/roles", json={"name": "billing"}, headers=admin_headers).json()

    response = client.patch(
        f"/roles/{created['id']}", json={"description": "Updated"}, headers=admin_headers
    )

    assert response.status_code == 200
    assert response.json()["description"] == "Updated"


def test_update_role_rejects_non_admin(
    client: TestClient, admin_headers: dict[str, str], member_headers: dict[str, str]
):
    created = client.post("/roles", json={"name": "billing"}, headers=admin_headers).json()

    response = client.patch(
        f"/roles/{created['id']}", json={"description": "Updated"}, headers=member_headers
    )

    assert response.status_code == 403


def test_update_role_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.patch(
        f"/roles/{uuid.uuid4()}", json={"description": "Updated"}, headers=admin_headers
    )

    assert response.status_code == 404


def test_update_role_rejects_duplicate_name(client: TestClient, admin_headers: dict[str, str]):
    client.post("/roles", json={"name": "billing"}, headers=admin_headers)
    other = client.post("/roles", json={"name": "support"}, headers=admin_headers).json()

    response = client.patch(
        f"/roles/{other['id']}", json={"name": "billing"}, headers=admin_headers
    )

    assert response.status_code == 409


def test_delete_role(client: TestClient, admin_headers: dict[str, str]):
    created = client.post("/roles", json={"name": "billing"}, headers=admin_headers).json()

    response = client.delete(f"/roles/{created['id']}", headers=admin_headers)

    assert response.status_code == 204
    assert client.get(f"/roles/{created['id']}", headers=admin_headers).status_code == 404


def test_delete_role_rejects_non_admin(
    client: TestClient, admin_headers: dict[str, str], member_headers: dict[str, str]
):
    created = client.post("/roles", json={"name": "billing"}, headers=admin_headers).json()

    response = client.delete(f"/roles/{created['id']}", headers=member_headers)

    assert response.status_code == 403


def test_delete_role_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.delete(f"/roles/{uuid.uuid4()}", headers=admin_headers)

    assert response.status_code == 404


def test_assign_role(
    client: TestClient,
    admin_headers: dict[str, str],
    member_user: User,
):
    created = client.post("/roles", json={"name": "billing"}, headers=admin_headers).json()

    response = client.post(
        f"/roles/{created['id']}/users/{member_user.id}", headers=admin_headers
    )

    assert response.status_code == 204


def test_assign_role_rejects_duplicate(
    client: TestClient, admin_headers: dict[str, str], member_user: User
):
    created = client.post("/roles", json={"name": "billing"}, headers=admin_headers).json()
    client.post(f"/roles/{created['id']}/users/{member_user.id}", headers=admin_headers)

    response = client.post(
        f"/roles/{created['id']}/users/{member_user.id}", headers=admin_headers
    )

    assert response.status_code == 409


def test_assign_role_rejects_missing_role(
    client: TestClient, admin_headers: dict[str, str], member_user: User
):
    response = client.post(
        f"/roles/{uuid.uuid4()}/users/{member_user.id}", headers=admin_headers
    )

    assert response.status_code == 404


def test_assign_role_rejects_missing_user(client: TestClient, admin_headers: dict[str, str]):
    created = client.post("/roles", json={"name": "billing"}, headers=admin_headers).json()

    response = client.post(
        f"/roles/{created['id']}/users/{uuid.uuid4()}", headers=admin_headers
    )

    assert response.status_code == 404


def test_assign_role_rejects_non_admin(
    client: TestClient,
    admin_headers: dict[str, str],
    member_headers: dict[str, str],
    member_user: User,
):
    created = client.post("/roles", json={"name": "billing"}, headers=admin_headers).json()

    response = client.post(
        f"/roles/{created['id']}/users/{member_user.id}", headers=member_headers
    )

    assert response.status_code == 403


def test_remove_role(client: TestClient, admin_headers: dict[str, str], member_user: User):
    created = client.post("/roles", json={"name": "billing"}, headers=admin_headers).json()
    client.post(f"/roles/{created['id']}/users/{member_user.id}", headers=admin_headers)

    response = client.delete(
        f"/roles/{created['id']}/users/{member_user.id}", headers=admin_headers
    )

    assert response.status_code == 204


def test_remove_role_not_assigned(
    client: TestClient, admin_headers: dict[str, str], member_user: User
):
    created = client.post("/roles", json={"name": "billing"}, headers=admin_headers).json()

    response = client.delete(
        f"/roles/{created['id']}/users/{member_user.id}", headers=admin_headers
    )

    assert response.status_code == 404


def test_remove_role_rejects_non_admin(
    client: TestClient,
    admin_headers: dict[str, str],
    member_headers: dict[str, str],
    member_user: User,
):
    created = client.post("/roles", json={"name": "billing"}, headers=admin_headers).json()
    client.post(f"/roles/{created['id']}/users/{member_user.id}", headers=admin_headers)

    response = client.delete(
        f"/roles/{created['id']}/users/{member_user.id}", headers=member_headers
    )

    assert response.status_code == 403
