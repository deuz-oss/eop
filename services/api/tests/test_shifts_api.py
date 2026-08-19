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

# Shift Authorization: reads remain open to any authenticated user;
# create/update/delete are Role Based (`RequireRole("admin")`), reopened per
# CTO decision H2 -- mirrors `test_locations_api.py`'s exact fixture/test
# pattern.

DEFAULT_TIMES = {"start_time": "09:00:00", "end_time": "17:00:00"}


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


def _create_shift(
    client: TestClient,
    headers: dict[str, str],
    *,
    code: str = "MORNING",
    name: str = "Morning Shift",
    **overrides,
) -> dict:
    body = {"code": code, "name": name, **DEFAULT_TIMES, **overrides}
    response = client.post("/hr/shifts", json=body, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_create_shift_requires_authentication(client: TestClient):
    response = client.post(
        "/hr/shifts", json={"code": "MORNING", "name": "Morning Shift", **DEFAULT_TIMES}
    )

    assert response.status_code == 401


def test_list_shifts_requires_authentication(client: TestClient):
    response = client.get("/hr/shifts")

    assert response.status_code == 401


def test_get_shift_requires_authentication(client: TestClient):
    response = client.get(f"/hr/shifts/{uuid.uuid4()}")

    assert response.status_code == 401


def test_update_shift_requires_authentication(client: TestClient):
    response = client.put(f"/hr/shifts/{uuid.uuid4()}", json={"name": "New Name"})

    assert response.status_code == 401


def test_delete_shift_requires_authentication(client: TestClient):
    response = client.delete(f"/hr/shifts/{uuid.uuid4()}")

    assert response.status_code == 401


# --- authorization: reads open to any authenticated user, writes admin-only ---


def test_list_shifts_allows_non_admin(client: TestClient, user_headers: dict[str, str]):
    response = client.get("/hr/shifts", headers=user_headers)

    assert response.status_code == 200


def test_get_shift_allows_non_admin(client: TestClient, user_headers: dict[str, str]):
    response = client.get(f"/hr/shifts/{uuid.uuid4()}", headers=user_headers)

    # 404 (not 403) proves the request reached the service layer -- the
    # non-admin caller was not rejected by authorization.
    assert response.status_code == 404


def test_list_shifts_allows_admin(client: TestClient, admin_headers: dict[str, str]):
    response = client.get("/hr/shifts", headers=admin_headers)

    assert response.status_code == 200


def test_create_shift_rejects_non_admin(client: TestClient, user_headers: dict[str, str]):
    response = client.post(
        "/hr/shifts",
        json={"code": "MORNING", "name": "Morning Shift", **DEFAULT_TIMES},
        headers=user_headers,
    )

    assert response.status_code == 403


def test_update_shift_rejects_non_admin(client: TestClient, user_headers: dict[str, str]):
    response = client.put(
        f"/hr/shifts/{uuid.uuid4()}", json={"name": "New Name"}, headers=user_headers
    )

    assert response.status_code == 403


def test_delete_shift_rejects_non_admin(client: TestClient, user_headers: dict[str, str]):
    response = client.delete(f"/hr/shifts/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 403


# --- create ---------------------------------------------------------------


def test_create_shift(client: TestClient, admin_headers: dict[str, str]):
    body = _create_shift(client, admin_headers)

    assert body["code"] == "MORNING"
    assert body["name"] == "Morning Shift"
    assert body["description"] is None
    assert body["start_time"] == "09:00:00"
    assert body["end_time"] == "17:00:00"
    assert body["break_duration_minutes"] == 0
    assert body["grace_period_minutes"] == 0
    uuid.UUID(body["id"])


def test_create_shift_rejects_blank_name(client: TestClient, admin_headers: dict[str, str]):
    response = client.post(
        "/hr/shifts",
        json={"code": "MORNING", "name": "", **DEFAULT_TIMES},
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_create_shift_rejects_duplicate_code(client: TestClient, admin_headers: dict[str, str]):
    _create_shift(client, admin_headers, code="MORNING")

    response = client.post(
        "/hr/shifts",
        json={"code": "MORNING", "name": "Other", **DEFAULT_TIMES},
        headers=admin_headers,
    )

    assert response.status_code == 409


def test_create_shift_rejects_equal_start_and_end_time(
    client: TestClient, admin_headers: dict[str, str]
):
    response = client.post(
        "/hr/shifts",
        json={
            "code": "MORNING",
            "name": "Morning Shift",
            "start_time": "09:00:00",
            "end_time": "09:00:00",
        },
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_create_shift_allows_overnight_shift(client: TestClient, admin_headers: dict[str, str]):
    body = _create_shift(
        client,
        admin_headers,
        code="NIGHT",
        name="Night Shift",
        start_time="22:00:00",
        end_time="06:00:00",
    )

    assert body["start_time"] == "22:00:00"
    assert body["end_time"] == "06:00:00"


def test_create_shift_rejects_negative_break_duration(
    client: TestClient, admin_headers: dict[str, str]
):
    response = client.post(
        "/hr/shifts",
        json={
            "code": "MORNING",
            "name": "Morning Shift",
            **DEFAULT_TIMES,
            "break_duration_minutes": -1,
        },
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_get_shift(client: TestClient, admin_headers: dict[str, str]):
    created = _create_shift(client, admin_headers, code="MORNING", name="Morning Shift")

    response = client.get(f"/hr/shifts/{created['id']}", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["name"] == "Morning Shift"


def test_get_shift_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.get(f"/hr/shifts/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_list_shifts(client: TestClient, admin_headers: dict[str, str]):
    _create_shift(client, admin_headers, code="MORNING", name="Morning Shift")
    _create_shift(
        client,
        admin_headers,
        code="NIGHT",
        name="Night Shift",
        start_time="22:00:00",
        end_time="06:00:00",
    )

    response = client.get("/hr/shifts", headers=admin_headers)

    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert {"Morning Shift", "Night Shift"}.issubset(names)


def test_list_shifts_paginated_default_pagination(
    client: TestClient, admin_headers: dict[str, str]
):
    for i in range(3):
        _create_shift(client, admin_headers, code=f"S{i}", name=f"Shift {i}")

    response = client.get("/hr/shifts/paginated", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 0
    assert body["limit"] == 50
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_list_shifts_paginated_custom_offset(client: TestClient, admin_headers: dict[str, str]):
    for i in range(5):
        _create_shift(client, admin_headers, code=f"S{i}", name=f"Shift {i}")

    response = client.get("/hr/shifts/paginated", headers=admin_headers, params={"offset": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 2
    assert body["total"] == 5
    assert len(body["items"]) == 3


def test_list_shifts_paginated_search_by_name(client: TestClient, admin_headers: dict[str, str]):
    _create_shift(client, admin_headers, code="MORNING", name="Morning Shift")
    _create_shift(
        client,
        admin_headers,
        code="NIGHT",
        name="Night Shift",
        start_time="22:00:00",
        end_time="06:00:00",
    )

    response = client.get("/hr/shifts/paginated", headers=admin_headers, params={"q": "morning"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Morning Shift"


def test_list_shifts_paginated_search_by_code(client: TestClient, admin_headers: dict[str, str]):
    _create_shift(client, admin_headers, code="MORNING-01", name="Early")
    _create_shift(
        client,
        admin_headers,
        code="NIGHT-01",
        name="Late",
        start_time="22:00:00",
        end_time="06:00:00",
    )

    response = client.get("/hr/shifts/paginated", headers=admin_headers, params={"q": "morning"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["code"] == "MORNING-01"


def test_list_shifts_paginated_no_query_returns_all(
    client: TestClient, admin_headers: dict[str, str]
):
    _create_shift(client, admin_headers, code="MORNING", name="Morning Shift")
    _create_shift(
        client,
        admin_headers,
        code="NIGHT",
        name="Night Shift",
        start_time="22:00:00",
        end_time="06:00:00",
    )

    response = client.get("/hr/shifts/paginated", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_update_shift(client: TestClient, admin_headers: dict[str, str]):
    created = _create_shift(client, admin_headers, name="Before")

    response = client.put(
        f"/hr/shifts/{created['id']}", json={"name": "After"}, headers=admin_headers
    )

    assert response.status_code == 200
    assert response.json()["name"] == "After"


def test_update_shift_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.put(
        f"/hr/shifts/{uuid.uuid4()}", json={"name": "After"}, headers=admin_headers
    )

    assert response.status_code == 404


def test_update_shift_rejects_duplicate_code(client: TestClient, admin_headers: dict[str, str]):
    _create_shift(client, admin_headers, code="MORNING")
    other = _create_shift(
        client, admin_headers, code="NIGHT", start_time="22:00:00", end_time="06:00:00"
    )

    response = client.put(
        f"/hr/shifts/{other['id']}", json={"code": "MORNING"}, headers=admin_headers
    )

    assert response.status_code == 409


def test_update_shift_rejects_invalid_start_end(client: TestClient, admin_headers: dict[str, str]):
    created = _create_shift(client, admin_headers)

    response = client.put(
        f"/hr/shifts/{created['id']}",
        json={"start_time": "17:00:00", "end_time": "17:00:00"},
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_update_shift_rejects_partial_payload_colliding_with_persisted_end_time(
    client: TestClient, admin_headers: dict[str, str]
):
    created = _create_shift(client, admin_headers, start_time="09:00:00", end_time="17:00:00")

    response = client.put(
        f"/hr/shifts/{created['id']}", json={"start_time": "17:00:00"}, headers=admin_headers
    )

    assert response.status_code == 422


def test_update_shift_rejects_negative_break_duration(
    client: TestClient, admin_headers: dict[str, str]
):
    created = _create_shift(client, admin_headers)

    response = client.put(
        f"/hr/shifts/{created['id']}",
        json={"break_duration_minutes": -1},
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_delete_shift(client: TestClient, admin_headers: dict[str, str]):
    created = _create_shift(client, admin_headers, name="To Delete")

    response = client.delete(f"/hr/shifts/{created['id']}", headers=admin_headers)

    assert response.status_code == 204
    assert client.get(f"/hr/shifts/{created['id']}", headers=admin_headers).status_code == 404


def test_delete_shift_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.delete(f"/hr/shifts/{uuid.uuid4()}", headers=admin_headers)

    assert response.status_code == 404
