import asyncio
import uuid
from collections.abc import Generator

import pytest
from conftest import clean_database
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.core.security import hash_password
from eop_api.main import app
from eop_api.models.user import User
from eop_api.repositories.role import RoleRepository
from eop_api.repositories.user import UserRepository

# Store Authorization: Role Based (`RequireRole("admin")`), mirroring
# `test_job_requisitions_api.py`'s exact fixture/test pattern.


_tables = pytest.fixture(autouse=True)(clean_database)


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


async def _seed_admin(user_id: uuid.UUID) -> None:
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


def _create_store_type(
    client: TestClient, headers: dict[str, str], *, code: str = "MT", **overrides
) -> dict:
    body = {"code": code, "name": "Modern Trade", **overrides}
    response = client.post("/store-types", json=body, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_create_store_type_requires_authentication(client: TestClient):
    response = client.post("/store-types", json={"code": "MT", "name": "Modern Trade"})
    assert response.status_code == 401


def test_list_store_types_requires_authentication(client: TestClient):
    assert client.get("/store-types").status_code == 401


def test_get_store_type_requires_authentication(client: TestClient):
    assert client.get(f"/store-types/{uuid.uuid4()}").status_code == 401


def test_update_store_type_requires_authentication(client: TestClient):
    response = client.put(f"/store-types/{uuid.uuid4()}", json={"name": "x"})
    assert response.status_code == 401


def test_delete_store_type_requires_authentication(client: TestClient):
    assert client.delete(f"/store-types/{uuid.uuid4()}").status_code == 401


def test_create_store_type_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.post(
        "/store-types", json={"code": "MT", "name": "Modern Trade"}, headers=member_headers
    )
    assert response.status_code == 403


def test_list_store_types_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    assert client.get("/store-types", headers=member_headers).status_code == 403


def test_get_store_type_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.get(f"/store-types/{uuid.uuid4()}", headers=member_headers)
    assert response.status_code == 403


def test_update_store_type_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.put(
        f"/store-types/{uuid.uuid4()}", json={"name": "x"}, headers=member_headers
    )
    assert response.status_code == 403


def test_delete_store_type_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.delete(f"/store-types/{uuid.uuid4()}", headers=member_headers)
    assert response.status_code == 403


def test_create_store_type(client: TestClient, admin_headers: dict[str, str]):
    body = _create_store_type(client, admin_headers)

    assert body["code"] == "MT"
    assert body["name"] == "Modern Trade"
    uuid.UUID(body["id"])


def test_create_store_type_rejects_duplicate_code(
    client: TestClient, admin_headers: dict[str, str]
):
    _create_store_type(client, admin_headers, code="MT")

    response = client.post(
        "/store-types", json={"code": "MT", "name": "Other"}, headers=admin_headers
    )

    assert response.status_code == 409


def test_get_store_type(client: TestClient, admin_headers: dict[str, str]):
    created = _create_store_type(client, admin_headers)

    response = client.get(f"/store-types/{created['id']}", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["code"] == "MT"


def test_get_store_type_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.get(f"/store-types/{uuid.uuid4()}", headers=admin_headers)
    assert response.status_code == 404


def test_list_store_types_paginated(client: TestClient, admin_headers: dict[str, str]):
    _create_store_type(client, admin_headers)

    response = client.get("/store-types/paginated", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_update_store_type(client: TestClient, admin_headers: dict[str, str]):
    created = _create_store_type(client, admin_headers)

    response = client.put(
        f"/store-types/{created['id']}", json={"name": "Updated"}, headers=admin_headers
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated"


def test_update_store_type_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.put(f"/store-types/{uuid.uuid4()}", json={"name": "x"}, headers=admin_headers)
    assert response.status_code == 404


def test_delete_store_type(client: TestClient, admin_headers: dict[str, str]):
    created = _create_store_type(client, admin_headers)

    response = client.delete(f"/store-types/{created['id']}", headers=admin_headers)

    assert response.status_code == 204
    assert client.get(f"/store-types/{created['id']}", headers=admin_headers).status_code == 404


def test_delete_store_type_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.delete(f"/store-types/{uuid.uuid4()}", headers=admin_headers)
    assert response.status_code == 404
