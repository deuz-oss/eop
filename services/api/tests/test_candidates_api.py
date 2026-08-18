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

# Recruitment Authorization: Role Based (`RequireRole("admin")`), mirroring
# `test_payroll_runs_api.py`'s exact fixture/test pattern. `Candidate`
# carries PII (name/email/phone) -- this file pays particular attention to
# ensuring a non-admin authenticated user cannot read or mutate it.


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
    """Grants the `admin` role directly at the DB layer, mirroring
    `test_payroll_runs_api.py`'s `_seed_admin`."""
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
    """An authenticated user without the `admin` role."""
    return asyncio.run(_create_user(email="member@example.com", password="member-pass"))


@pytest.fixture
def member_headers(client: TestClient, member_user: User) -> dict[str, str]:
    response = client.post(
        "/auth/login", json={"email": "member@example.com", "password": "member-pass"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_candidate(
    client: TestClient, headers: dict[str, str], *, email: str = "ada@example.com", **overrides
) -> dict:
    body = {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "full_name": "Ada Lovelace",
        "email": email,
        **overrides,
    }
    response = client.post("/recruitment/candidates", json=body, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_create_candidate_requires_authentication(client: TestClient):
    response = client.post(
        "/recruitment/candidates",
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "full_name": "Ada Lovelace",
            "email": "ada@example.com",
        },
    )

    assert response.status_code == 401


def test_list_candidates_requires_authentication(client: TestClient):
    response = client.get("/recruitment/candidates")

    assert response.status_code == 401


def test_get_candidate_requires_authentication(client: TestClient):
    response = client.get(f"/recruitment/candidates/{uuid.uuid4()}")

    assert response.status_code == 401


def test_update_candidate_requires_authentication(client: TestClient):
    response = client.put(f"/recruitment/candidates/{uuid.uuid4()}", json={"full_name": "After"})

    assert response.status_code == 401


def test_delete_candidate_requires_authentication(client: TestClient):
    response = client.delete(f"/recruitment/candidates/{uuid.uuid4()}")

    assert response.status_code == 401


def test_create_candidate_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.post(
        "/recruitment/candidates",
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "full_name": "Ada Lovelace",
            "email": "ada@example.com",
        },
        headers=member_headers,
    )

    assert response.status_code == 403


def test_list_candidates_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.get("/recruitment/candidates", headers=member_headers)

    assert response.status_code == 403


def test_list_candidates_paginated_rejects_non_admin(
    client: TestClient, member_headers: dict[str, str]
):
    response = client.get("/recruitment/candidates/paginated", headers=member_headers)

    assert response.status_code == 403


def test_get_candidate_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.get(f"/recruitment/candidates/{uuid.uuid4()}", headers=member_headers)

    assert response.status_code == 403


def test_update_candidate_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.put(
        f"/recruitment/candidates/{uuid.uuid4()}",
        json={"full_name": "After"},
        headers=member_headers,
    )

    assert response.status_code == 403


def test_delete_candidate_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.delete(f"/recruitment/candidates/{uuid.uuid4()}", headers=member_headers)

    assert response.status_code == 403


def test_create_candidate(client: TestClient, admin_headers: dict[str, str]):
    body = _create_candidate(client, admin_headers)

    assert body["full_name"] == "Ada Lovelace"
    assert body["email"] == "ada@example.com"
    assert body["phone"] is None
    uuid.UUID(body["id"])


def test_create_candidate_rejects_duplicate_email(
    client: TestClient, admin_headers: dict[str, str]
):
    _create_candidate(client, admin_headers, email="ada@example.com")

    response = client.post(
        "/recruitment/candidates",
        json={
            "first_name": "Ada",
            "last_name": "Two",
            "full_name": "Ada Two",
            "email": "ada@example.com",
        },
        headers=admin_headers,
    )

    assert response.status_code == 409


def test_create_candidate_rejects_blank_name(client: TestClient, admin_headers: dict[str, str]):
    response = client.post(
        "/recruitment/candidates",
        json={
            "first_name": "",
            "last_name": "Lovelace",
            "full_name": "Ada Lovelace",
            "email": "ada@example.com",
        },
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_get_candidate(client: TestClient, admin_headers: dict[str, str]):
    created = _create_candidate(client, admin_headers)

    response = client.get(f"/recruitment/candidates/{created['id']}", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["full_name"] == "Ada Lovelace"


def test_get_candidate_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.get(f"/recruitment/candidates/{uuid.uuid4()}", headers=admin_headers)

    assert response.status_code == 404


def test_list_candidates(client: TestClient, admin_headers: dict[str, str]):
    _create_candidate(client, admin_headers, email="ada@example.com")
    _create_candidate(client, admin_headers, email="alan@example.com", full_name="Alan Turing")

    response = client.get("/recruitment/candidates", headers=admin_headers)

    assert response.status_code == 200
    names = {item["full_name"] for item in response.json()}
    assert {"Ada Lovelace", "Alan Turing"}.issubset(names)


def test_list_candidates_paginated(client: TestClient, admin_headers: dict[str, str]):
    for i in range(3):
        _create_candidate(client, admin_headers, email=f"c{i}@example.com", full_name=f"C {i}")

    response = client.get("/recruitment/candidates/paginated", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 0
    assert body["limit"] == 50
    assert body["total"] == 3


def test_update_candidate(client: TestClient, admin_headers: dict[str, str]):
    created = _create_candidate(client, admin_headers)

    response = client.put(
        f"/recruitment/candidates/{created['id']}",
        json={"full_name": "After"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "After"


def test_update_candidate_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.put(
        f"/recruitment/candidates/{uuid.uuid4()}",
        json={"full_name": "After"},
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_delete_candidate(client: TestClient, admin_headers: dict[str, str]):
    created = _create_candidate(client, admin_headers)

    response = client.delete(f"/recruitment/candidates/{created['id']}", headers=admin_headers)

    assert response.status_code == 204
    assert (
        client.get(f"/recruitment/candidates/{created['id']}", headers=admin_headers).status_code
        == 404
    )


def test_delete_candidate_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.delete(f"/recruitment/candidates/{uuid.uuid4()}", headers=admin_headers)

    assert response.status_code == 404
