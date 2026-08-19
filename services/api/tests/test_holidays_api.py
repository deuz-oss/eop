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

# Holiday Authorization: reads remain open to any authenticated user;
# create/update/delete are Role Based (`RequireRole("admin")`), reopened per
# CTO decision H2 -- mirrors `test_locations_api.py`'s exact fixture/test
# pattern.

DEFAULT_DATE = {"holiday_date": "2027-01-01"}


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


def _create_holiday(
    client: TestClient,
    headers: dict[str, str],
    *,
    code: str = "NEWYEAR",
    name: str = "New Year's Day",
    **overrides,
) -> dict:
    body = {"code": code, "name": name, **DEFAULT_DATE, **overrides}
    response = client.post("/hr/holidays", json=body, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_create_holiday_requires_authentication(client: TestClient):
    response = client.post(
        "/hr/holidays", json={"code": "NEWYEAR", "name": "New Year's Day", **DEFAULT_DATE}
    )

    assert response.status_code == 401


def test_list_holidays_requires_authentication(client: TestClient):
    response = client.get("/hr/holidays")

    assert response.status_code == 401


def test_get_holiday_requires_authentication(client: TestClient):
    response = client.get(f"/hr/holidays/{uuid.uuid4()}")

    assert response.status_code == 401


def test_update_holiday_requires_authentication(client: TestClient):
    response = client.put(f"/hr/holidays/{uuid.uuid4()}", json={"name": "New Name"})

    assert response.status_code == 401


def test_delete_holiday_requires_authentication(client: TestClient):
    response = client.delete(f"/hr/holidays/{uuid.uuid4()}")

    assert response.status_code == 401


# --- authorization: reads open to any authenticated user, writes admin-only ---


def test_list_holidays_allows_non_admin(client: TestClient, user_headers: dict[str, str]):
    response = client.get("/hr/holidays", headers=user_headers)

    assert response.status_code == 200


def test_get_holiday_allows_non_admin(client: TestClient, user_headers: dict[str, str]):
    response = client.get(f"/hr/holidays/{uuid.uuid4()}", headers=user_headers)

    # 404 (not 403) proves the request reached the service layer -- the
    # non-admin caller was not rejected by authorization.
    assert response.status_code == 404


def test_list_holidays_allows_admin(client: TestClient, admin_headers: dict[str, str]):
    response = client.get("/hr/holidays", headers=admin_headers)

    assert response.status_code == 200


def test_create_holiday_rejects_non_admin(client: TestClient, user_headers: dict[str, str]):
    response = client.post(
        "/hr/holidays",
        json={"code": "NEWYEAR", "name": "New Year's Day", **DEFAULT_DATE},
        headers=user_headers,
    )

    assert response.status_code == 403


def test_update_holiday_rejects_non_admin(client: TestClient, user_headers: dict[str, str]):
    response = client.put(
        f"/hr/holidays/{uuid.uuid4()}", json={"name": "New Name"}, headers=user_headers
    )

    assert response.status_code == 403


def test_delete_holiday_rejects_non_admin(client: TestClient, user_headers: dict[str, str]):
    response = client.delete(f"/hr/holidays/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 403


# --- create ---------------------------------------------------------------


def test_create_holiday(client: TestClient, admin_headers: dict[str, str]):
    body = _create_holiday(client, admin_headers)

    assert body["code"] == "NEWYEAR"
    assert body["name"] == "New Year's Day"
    assert body["description"] is None
    assert body["holiday_date"] == "2027-01-01"
    uuid.UUID(body["id"])


def test_create_holiday_rejects_blank_name(client: TestClient, admin_headers: dict[str, str]):
    response = client.post(
        "/hr/holidays",
        json={"code": "NEWYEAR", "name": "", **DEFAULT_DATE},
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_create_holiday_rejects_duplicate_code(client: TestClient, admin_headers: dict[str, str]):
    _create_holiday(client, admin_headers, code="NEWYEAR")

    response = client.post(
        "/hr/holidays",
        json={"code": "NEWYEAR", "name": "Other", "holiday_date": "2027-12-25"},
        headers=admin_headers,
    )

    assert response.status_code == 409


def test_create_holiday_rejects_duplicate_holiday_date(
    client: TestClient, admin_headers: dict[str, str]
):
    _create_holiday(client, admin_headers, code="NEWYEAR", holiday_date="2027-01-01")

    response = client.post(
        "/hr/holidays",
        json={"code": "OTHER", "name": "Other", "holiday_date": "2027-01-01"},
        headers=admin_headers,
    )

    assert response.status_code == 409


def test_get_holiday(client: TestClient, admin_headers: dict[str, str]):
    created = _create_holiday(client, admin_headers, code="NEWYEAR", name="New Year's Day")

    response = client.get(f"/hr/holidays/{created['id']}", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["name"] == "New Year's Day"


def test_get_holiday_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.get(f"/hr/holidays/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_list_holidays(client: TestClient, admin_headers: dict[str, str]):
    _create_holiday(client, admin_headers, code="NEWYEAR", name="New Year's Day")
    _create_holiday(
        client, admin_headers, code="INDEP", name="Independence Day", holiday_date="2027-08-17"
    )

    response = client.get("/hr/holidays", headers=admin_headers)

    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert {"New Year's Day", "Independence Day"}.issubset(names)


def test_list_holidays_paginated_default_pagination(
    client: TestClient, admin_headers: dict[str, str]
):
    for i in range(3):
        _create_holiday(
            client,
            admin_headers,
            code=f"H{i}",
            name=f"Holiday {i}",
            holiday_date=f"2027-01-0{i + 1}",
        )

    response = client.get("/hr/holidays/paginated", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 0
    assert body["limit"] == 50
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_list_holidays_paginated_custom_offset(client: TestClient, admin_headers: dict[str, str]):
    for i in range(5):
        _create_holiday(
            client,
            admin_headers,
            code=f"H{i}",
            name=f"Holiday {i}",
            holiday_date=f"2027-01-0{i + 1}",
        )

    response = client.get("/hr/holidays/paginated", headers=admin_headers, params={"offset": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 2
    assert body["total"] == 5
    assert len(body["items"]) == 3


def test_list_holidays_paginated_search_by_name(client: TestClient, admin_headers: dict[str, str]):
    _create_holiday(client, admin_headers, code="NEWYEAR", name="New Year's Day")
    _create_holiday(
        client, admin_headers, code="INDEP", name="Independence Day", holiday_date="2027-08-17"
    )

    response = client.get("/hr/holidays/paginated", headers=admin_headers, params={"q": "new year"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "New Year's Day"


def test_list_holidays_paginated_search_by_code(client: TestClient, admin_headers: dict[str, str]):
    _create_holiday(client, admin_headers, code="NEWYEAR-01", name="Early")
    _create_holiday(client, admin_headers, code="INDEP-01", name="Late", holiday_date="2027-08-17")

    response = client.get("/hr/holidays/paginated", headers=admin_headers, params={"q": "newyear"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["code"] == "NEWYEAR-01"


def test_list_holidays_paginated_no_query_returns_all(
    client: TestClient, admin_headers: dict[str, str]
):
    _create_holiday(client, admin_headers, code="NEWYEAR", name="New Year's Day")
    _create_holiday(
        client, admin_headers, code="INDEP", name="Independence Day", holiday_date="2027-08-17"
    )

    response = client.get("/hr/holidays/paginated", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_update_holiday(client: TestClient, admin_headers: dict[str, str]):
    created = _create_holiday(client, admin_headers, name="Before")

    response = client.put(
        f"/hr/holidays/{created['id']}", json={"name": "After"}, headers=admin_headers
    )

    assert response.status_code == 200
    assert response.json()["name"] == "After"


def test_update_holiday_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.put(
        f"/hr/holidays/{uuid.uuid4()}", json={"name": "After"}, headers=admin_headers
    )

    assert response.status_code == 404


def test_update_holiday_rejects_duplicate_code(client: TestClient, admin_headers: dict[str, str]):
    _create_holiday(client, admin_headers, code="NEWYEAR")
    other = _create_holiday(client, admin_headers, code="INDEP", holiday_date="2027-08-17")

    response = client.put(
        f"/hr/holidays/{other['id']}", json={"code": "NEWYEAR"}, headers=admin_headers
    )

    assert response.status_code == 409


def test_update_holiday_rejects_duplicate_holiday_date(
    client: TestClient, admin_headers: dict[str, str]
):
    _create_holiday(client, admin_headers, code="NEWYEAR", holiday_date="2027-01-01")
    other = _create_holiday(client, admin_headers, code="INDEP", holiday_date="2027-08-17")

    response = client.put(
        f"/hr/holidays/{other['id']}",
        json={"holiday_date": "2027-01-01"},
        headers=admin_headers,
    )

    assert response.status_code == 409


def test_delete_holiday(client: TestClient, admin_headers: dict[str, str]):
    created = _create_holiday(client, admin_headers, name="To Delete")

    response = client.delete(f"/hr/holidays/{created['id']}", headers=admin_headers)

    assert response.status_code == 204
    assert client.get(f"/hr/holidays/{created['id']}", headers=admin_headers).status_code == 404


def test_delete_holiday_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.delete(f"/hr/holidays/{uuid.uuid4()}", headers=admin_headers)

    assert response.status_code == 404
